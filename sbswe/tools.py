"""Built-in tools beyond bash. Each returns a dict with 'output'/'returncode'."""
import os
from pathlib import Path


def read_file(path, offset=1, limit=2000):
    p = Path(path)
    try:
        lines = p.read_text(errors="replace").splitlines(keepends=True)
    except Exception as e:
        return {"output": f"error: {e}", "returncode": 1}
    start = max(1, offset) - 1
    chunk = lines[start : start + limit]
    numbered = "".join(f"{i + start + 1}|{ln}" for i, ln in enumerate(chunk))
    return {"output": numbered or "(empty)", "returncode": 0}


def write_file(path, content):
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    except Exception as e:
        return {"output": f"error: {e}", "returncode": 1}
    return {"output": f"wrote {len(content)} bytes to {path}", "returncode": 0}


def list_dir(path="."):
    try:
        entries = sorted(os.listdir(path))
    except Exception as e:
        return {"output": f"error: {e}", "returncode": 1}
    return {"output": "\n".join(entries), "returncode": 0}


def find_files(root=".", glob="*"):
    out = []
    try:
        for p in Path(root).rglob(glob):
            out.append(str(p))
            if len(out) > 500:
                break
    except Exception as e:
        return {"output": f"error: {e}", "returncode": 1}
    return {"output": "\n".join(out) or "(none)", "returncode": 0}


def grep(pattern, root=".", glob="*"):
    import re
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return {"output": f"bad regex: {e}", "returncode": 1}
    hits = []
    for p in Path(root).rglob(glob):
        if not p.is_file():
            continue
        try:
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{p}:{i}:{line}")
                    if len(hits) > 200:
                        break
        except Exception:
            continue
        if len(hits) > 200:
            break
    return {"output": "\n".join(hits) or "(no matches)", "returncode": 0}
