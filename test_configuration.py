import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner
from sbswe.cli import app


class ConfigurationTests(unittest.TestCase):
    def test_configure_saves_endpoint_and_rotates_key_without_exposing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.yaml'
            env = root / '.env'
            with patch('sbswe.cli.USER_CONFIG_PATH', config), patch('sbswe.cli.PROJECT_ROOT', root):
                result = CliRunner().invoke(app, ['--configure'], input='openrouter/vendor/model\nhttps://openrouter.ai/api/v1\ntest-secret-one\n')
                self.assertEqual(result.exit_code, 0, result.output)
                data = yaml.safe_load(config.read_text())
                self.assertEqual(data['model']['model_name'], 'openrouter/vendor/model')
                self.assertEqual(data['endpoints']['openrouter'], data['model'])
                self.assertNotIn('test-secret-one', config.read_text() + result.output)
                self.assertIn('test-secret-one', env.read_text())
                self.assertEqual(env.stat().st_mode & 0o777, 0o600)
                result = CliRunner().invoke(app, ['--reauth'], input='test-secret-two\n')
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertNotIn('test-secret-two', result.output)
                self.assertNotIn('test-secret-one', env.read_text())
                self.assertIn('test-secret-two', env.read_text())
                self.assertEqual(yaml.safe_load(config.read_text())['model'], data['model'])

    def test_invalid_endpoint_url_does_not_write_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('sbswe.cli.USER_CONFIG_PATH', root / 'config.yaml'), patch('sbswe.cli.PROJECT_ROOT', root):
                result = CliRunner().invoke(app, ['--configure'], input='openai/model\nhttps://user:password@example.com/v1\n')
                self.assertNotEqual(result.exit_code, 0)
                self.assertFalse((root / 'config.yaml').exists())
                self.assertFalse((root / '.env').exists())

    def test_switching_saved_endpoints_preserves_both(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.yaml'
            with patch('sbswe.cli.USER_CONFIG_PATH', config), patch('sbswe.cli.PROJECT_ROOT', root):
                runner = CliRunner()
                for answers in ['openai/one\n\nkey-one\n', 'anthropic/two\n\nkey-two\n', 'openai/one\n\ny\n\n']:
                    result = runner.invoke(app, ['--configure'], input=answers)
                    self.assertEqual(result.exit_code, 0, result.output)
                data = yaml.safe_load(config.read_text())
                self.assertEqual(set(data['endpoints']), {'openai', 'anthropic'})
                self.assertEqual(data['active_endpoint'], 'openai')
                self.assertEqual(data['model']['model_name'], 'openai/one')
                self.assertEqual(data['model']['api_key'], '${SBSWE_ENDPOINT_OPENAI_API_KEY}')

    def test_model_picker_saves_selection_without_expanding_secret_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.yaml'
            endpoint = {'model_name': 'openrouter/vendor/old', 'api_key': '${PRIVATE_KEY}'}
            config.write_text(yaml.safe_dump({'active_endpoint': 'router', 'model': endpoint, 'endpoints': {'router': endpoint}}))
            with patch('sbswe.cli.USER_CONFIG_PATH', config), patch('sbswe.configuration.fetch_models', return_value=['vendor/one', 'vendor/two']):
                result = CliRunner().invoke(app, ['--models'], input='1\ntwo\n1\n')
                self.assertEqual(result.exit_code, 0, result.output)
                data = yaml.safe_load(config.read_text())
                self.assertEqual(data['model']['model_name'], 'openrouter/vendor/two')
                self.assertEqual(data['endpoints']['router'], data['model'])
                self.assertEqual(data['model']['api_key'], '${PRIVATE_KEY}')

    def test_model_picker_falls_back_without_leaking_provider_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.yaml'
            endpoint = {'model_name': 'openai/old'}
            config.write_text(yaml.safe_dump({'endpoints': {'custom': endpoint}}))
            with patch('sbswe.cli.USER_CONFIG_PATH', config), patch('sbswe.configuration.fetch_models', side_effect=RuntimeError('private-provider-error')):
                result = CliRunner().invoke(app, ['--models'], input='1\nopenai/new\n')
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertNotIn('private-provider-error', result.output)
                self.assertEqual(yaml.safe_load(config.read_text())['model']['model_name'], 'openai/new')

    def test_saved_non_openai_provider_ignores_generic_base(self):
        from sbswe import cli
        cfg = {'model': {'model_name': 'anthropic/model', 'api_key': 'selected-key'}}
        with patch.object(cli, 'load_config', return_value=cfg), patch.dict(os.environ, {'OPENAI_API_BASE': 'https://unrelated.example/v1'}), patch.object(cli, 'Model') as model, patch.object(cli, 'Agent'):
            result = CliRunner().invoke(app, ['--task', 'test'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn('api_base', model.call_args.kwargs['model_kwargs'])

    def test_endpoint_name_collision_never_overwrites_other_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.yaml'
            with patch('sbswe.cli.USER_CONFIG_PATH', config), patch('sbswe.cli.PROJECT_ROOT', root):
                for name, key in [('my-server', 'first-key'), ('my_server', 'second-key')]:
                    result = CliRunner().invoke(app, ['--configure'], input=f'openai/test\nhttps://{name}.example/v1\n{name}\n{key}\n')
                    self.assertEqual(result.exit_code, 0, result.output)
                data = yaml.safe_load(config.read_text())
                self.assertNotEqual(data['endpoints']['my-server']['api_key'], data['endpoints']['my_server']['api_key'])
                from dotenv import dotenv_values
                values = dotenv_values(root / '.env')
                for name, key in [('my-server', 'first-key'), ('my_server', 'second-key')]:
                    self.assertEqual(values[data['endpoints'][name]['api_key'][2:-1]], key)

    def test_cross_provider_model_override_does_not_reuse_saved_key(self):
        from sbswe import cli
        cfg = {'model': {'model_name': 'openrouter/vendor/model', 'api_key': 'router-key'}}
        with patch.object(cli, 'load_config', return_value=cfg), patch.object(cli, 'Model') as model:
            result = CliRunner().invoke(app, ['--task', 'test', '-m', 'anthropic/model', '--yolo'])
            self.assertNotEqual(result.exit_code, 0)
            model.assert_not_called()

    def test_unknown_host_asks_for_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('sbswe.cli.USER_CONFIG_PATH', root / 'config.yaml'), patch('sbswe.cli.PROJECT_ROOT', root):
                result = CliRunner().invoke(app, ['--configure'], input='openai/custom\nhttps://private.example/v1\nmy-server\n\n')
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn('Could not identify endpoint', result.output)
                self.assertEqual(yaml.safe_load((root / 'config.yaml').read_text())['active_endpoint'], 'my-server')

    def test_host_matching_does_not_accept_lookalike_domains(self):
        from sbswe.configuration import detect_endpoint_name
        self.assertEqual(detect_endpoint_name('openai/model', 'https://openrouter.ai/api/v1'), 'openrouter')
        self.assertEqual(detect_endpoint_name('openai/model', 'https://openrouter.ai.attacker.example/v1'), '')
        self.assertEqual(detect_endpoint_name('anthropic/model', ''), 'anthropic')
        self.assertEqual(detect_endpoint_name('unknown/model', ''), '')

    def test_selected_endpoint_does_not_use_unrelated_openai_key(self):
        from sbswe import cli
        cfg = {'model': {'model_name': 'openrouter/vendor/model', 'api_key': 'selected-key', 'api_base': 'https://openrouter.ai/api/v1'}}
        with patch.object(cli, 'load_config', return_value=cfg), patch.dict(os.environ, {'OPENAI_API_KEY': 'unrelated-key', 'OPENAI_API_BASE': 'https://unrelated.example/v1'}), patch.object(cli, 'Model') as model, patch.object(cli, 'Agent'):
            result = CliRunner().invoke(app, ['--task', 'test'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(model.call_args.kwargs['model_kwargs']['api_key'], 'selected-key')
            self.assertEqual(model.call_args.kwargs['model_kwargs']['api_base'], 'https://openrouter.ai/api/v1')


if __name__ == '__main__':
    unittest.main()
