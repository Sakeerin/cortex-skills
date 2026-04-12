#!/usr/bin/env python3
"""
env_loader.py — Load AI Skills config from .env files

Search order:
  1. ~/.ai-skills.env
  2. .ai-skills.env  (current directory)
  3. .env            (current directory, fallback)

Usage:
  from env_loader import load_env, get, require
  load_env()
  data_dir = get("AI_SKILLS_DATA_DIR", "~/.ai-skills-data")
"""

import os
from pathlib import Path

_loaded = False


def load_env() -> None:
    """Load env vars from config files. Safe to call multiple times."""
    global _loaded
    if _loaded:
        return

    candidates = [
        Path.home() / ".ai-skills.env",
        Path.cwd() / ".ai-skills.env",
        Path.cwd() / ".env",
    ]

    for path in candidates:
        if path.exists():
            _parse_env_file(path)

    _loaded = True


def _parse_env_file(path: Path) -> None:
    """Parse a .env file and set environment variables (does not override existing)."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get(key: str, default: str = None) -> str:
    """Get env var, loading config files first."""
    load_env()
    return os.environ.get(key, default)


def require(key: str) -> str:
    """Get env var or raise if not set."""
    load_env()
    value = os.environ.get(key)
    if value is None:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set.\n"
            f"Add it to ~/.ai-skills.env or set it in your shell."
        )
    return value


def get_data_dir() -> Path:
    """Return the AI Skills data directory, creating it if needed."""
    raw = get("AI_SKILLS_DATA_DIR", str(Path.home() / ".ai-skills-data"))
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    load_env()
    print("AI Skills env loader — current config:")
    keys = ["AI_PROVIDER", "AI_MODEL", "AI_API_KEY", "AI_BASE_URL", "AI_SKILLS_DATA_DIR"]
    for k in keys:
        v = os.environ.get(k)
        if v:
            display = v[:8] + "..." if len(v) > 12 and "KEY" in k else v
            print(f"  {k}={display}")
        else:
            print(f"  {k}=(not set)")
