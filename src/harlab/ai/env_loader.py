"""Minimal, zero-dependency .env loader for local HARLAB configuration.

Reads KEY=VALUE pairs from a local `.env` file into `os.environ` without
overwriting variables already set in the process environment. Never logs values.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_local_env(env_path: str | Path | None = None) -> bool:
    """Load key=value pairs from `.env` if present. Returns True if a file was loaded."""
    if env_path is not None:
        candidates = [Path(env_path)]
    else:
        cwd_env = Path.cwd() / ".env"
        repo_env = Path(__file__).resolve().parents[3] / ".env"
        candidates = [cwd_env] if cwd_env == repo_env else [cwd_env, repo_env]

    for path in candidates:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
        return True
    return False
