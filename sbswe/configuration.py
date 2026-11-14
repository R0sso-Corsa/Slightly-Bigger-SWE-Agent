"""Interactive endpoint setup; credentials never enter YAML."""
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import typer
import yaml
from dotenv import set_key


def detect_endpoint_name(model: str, base: str) -> str:
    """Infer a display name locally, never by sending a key to a server."""
    hosts = {
        'api.openai.com': 'openai', 'openrouter.ai': 'openrouter',
        'api.anthropic.com': 'anthropic', 'api.deepseek.com': 'deepseek',
        'api.groq.com': 'groq', 'api.mistral.ai': 'mistral',
        'generativelanguage.googleapis.com': 'gemini', 'api.x.ai': 'xai',
    }
    if base:
        host = urlsplit(base).hostname
        return hosts.get(host or '', '')
    provider = model.split('/', 1)[0]
    known = {'openai', 'openrouter', 'anthropic', 'gemini', 'groq', 'mistral',
             'deepseek', 'xai', 'together_ai', 'deepinfra', 'ollama', 'chatgpt'}
    return provider if provider in known else ''


def configure(config_path: Path, env_path: Path, reauth: bool = False):
    # Read raw YAML: do not expand credentials before writing it back.
    data = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(data, dict):
        raise typer.BadParameter('Config must be a YAML mapping.')
    endpoints = data.setdefault('endpoints', {})
    if not isinstance(endpoints, dict):
        raise typer.BadParameter('endpoints must be a YAML mapping.')
    typer.echo('Saved endpoints: ' + (', '.join(endpoints) or '(none)'))
    name = data.get('active_endpoint', '')
    if reauth:
        if name not in endpoints:
            name = typer.prompt('Endpoint name')
        if name not in endpoints:
            raise typer.BadParameter('Unknown endpoint. Run --configure first.')
        endpoint = dict(endpoints[name])
        typer.echo(f'Using endpoint: {name}')
    else:
        # Start with the model: asking for a name first prevents inference.
        model = typer.prompt('LiteLLM model (provider/model)').strip()
        if '/' not in model or any(c.isspace() for c in model):
            raise typer.BadParameter('Model must use provider/model, e.g. openai/my-model.')
        base = typer.prompt('Base URL (blank for provider default)', default='').strip()
        if base:
            url = urlsplit(base)
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise typer.BadParameter('Use an http(s) base URL without credentials, query or fragment.')
        matches = [saved for saved, settings in endpoints.items()
                   if settings.get('model_name') == model and settings.get('api_base', '').rstrip('/') == base.rstrip('/')]
        name = matches[0] if len(matches) == 1 else detect_endpoint_name(model, base)
        if name in endpoints and endpoints[name].get('api_base', '').rstrip('/') != base.rstrip('/'):
            name = ''  # Do not silently replace another server's saved credentials.
        if not name:
            name = typer.prompt('Could not identify endpoint; enter endpoint name')
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', name):
            raise typer.BadParameter('Use a lowercase name starting with a letter (letters, digits, - or _).')
        if name in endpoints:
            typer.confirm(f'Update saved endpoint {name}?', abort=True)
        typer.echo(f'Using endpoint: {name}')
        endpoint = {'model_name': model}
        if base:
            endpoint['api_base'] = base
    key = typer.prompt('API key (blank to keep existing / no key)', default='', hide_input=True, show_default=False)
    variable = 'SBSWE_ENDPOINT_' + name.upper().replace('_', '_5F').replace('-', '_2D') + '_API_KEY'
    if key:
        if any(c in key for c in '\r\n\x00'):
            raise typer.BadParameter('API key must be a single line.')
        env_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(env_path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
        env_path.chmod(0o600)
        set_key(str(env_path), variable, key)
        env_path.chmod(0o600)
        endpoint['api_key'] = '${' + variable + '}'
    elif reauth:
        typer.echo('No key entered; unchanged.')
        return
    elif endpoints.get(name, {}).get('api_key'):
        endpoint['api_key'] = endpoints[name]['api_key']
    endpoints[name] = endpoint
    data['active_endpoint'] = name
    data['model'] = dict(endpoint)
    save_config(config_path, data)
    typer.echo(f'Saved endpoint {name}. Restart sbswe to use it. Keys are stored only in {env_path}.')


def fetch_models(endpoint):
    import json
    import ssl
    import certifi
    from urllib.request import Request, HTTPRedirectHandler, HTTPSHandler, build_opener
    from sbswe.cli import _expand_env

    provider = endpoint['model_name'].split('/', 1)[0]
    defaults = {'openrouter': 'https://openrouter.ai/api/v1',
                'openai': 'https://api.openai.com/v1',
                'anthropic': 'https://api.anthropic.com/v1',
                'groq': 'https://api.groq.com/openai/v1',
                'deepseek': 'https://api.deepseek.com/v1',
                'mistral': 'https://api.mistral.ai/v1'}
    base = endpoint.get('api_base') or defaults.get(provider)
    if not base:
        raise ValueError('This provider has no supported model-list endpoint.')
    url = urlsplit(base)
    if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Invalid model-list base URL.')
    key = _expand_env(endpoint.get('api_key', ''))
    if not key:
        key = os.environ.get(provider.upper() + '_API_KEY', '')
    headers = {'Accept': 'application/json'}
    if key:
        if provider == 'anthropic':
            headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
        else:
            headers['Authorization'] = 'Bearer ' + key

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # Never forward credentials to a redirected host.

    request = Request(base.rstrip('/') + '/models', headers=headers)
    context = ssl.create_default_context()
    context.load_verify_locations(certifi.where())
    with build_opener(NoRedirect(), HTTPSHandler(context=context)).open(request, timeout=15) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError('Model list exceeds size limit.')
    payload = json.loads(raw)
    return sorted({item['id'] for item in payload.get('data', [])
                   if isinstance(item, dict) and isinstance(item.get('id'), str)
                   and item['id'] and not any(c.isspace() for c in item['id'])})


def pick_number(label: str, count: int) -> int:
    while True:
        choice = typer.prompt(label, type=int)
        if 1 <= choice <= count:
            return choice
        typer.echo(f'Choose a number from 1 to {count}.')


def pick_model(config_path: Path):
    data = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get('endpoints'), dict) or not data['endpoints']:
        typer.echo('No saved endpoints. Run --configure first.')
        return
    names = list(data['endpoints'])
    for index, name in enumerate(names, 1):
        typer.echo(f'{index}. {name}')
    choice = pick_number('Endpoint number', len(names))
    name = names[choice - 1]
    endpoint = dict(data['endpoints'][name])
    provider = endpoint['model_name'].split('/', 1)[0]
    try:
        models = fetch_models(endpoint)
    except Exception:
        # Provider errors may embed credentials or response bodies: do not print them.
        typer.echo('Could not list models (unsupported API, credentials or connection).')
        models = []
    if models:
        query = typer.prompt('Search models (blank for all)', default='').lower()
        matches = [model for model in models if query in model.lower()]
        while not matches:
            query = typer.prompt('No matches. Search again').lower()
            matches = [model for model in models if query in model.lower()]
        for index, model in enumerate(matches, 1):
            typer.echo(f'{index}. {model}')
        choice = pick_number('Model number', len(matches))
        model = matches[choice - 1]
        model = model if model.startswith(provider + '/') else provider + '/' + model
    else:
        model = typer.prompt('Enter model manually (provider/model)').strip()
        if '/' not in model or any(c.isspace() for c in model):
            raise typer.BadParameter('Use provider/model.')
        if not model.startswith(provider + '/'):
            raise typer.BadParameter('Keep the selected endpoint provider; configure a new endpoint to change providers.')
    endpoint['model_name'] = model
    data['endpoints'][name] = endpoint
    data['active_endpoint'] = name
    data['model'] = dict(endpoint)
    save_config(config_path, data)
    typer.echo(f'Default model saved: {model}. Takes effect on the next chat (unless overridden by flags/env/config).')


def save_config(config_path: Path, data):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement keeps an interrupted write from truncating the config.
    fd, temporary = tempfile.mkstemp(dir=config_path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            yaml.safe_dump(data, output, sort_keys=False)
        os.replace(temporary, config_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
