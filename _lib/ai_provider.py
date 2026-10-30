#!/usr/bin/env python3
"""
ai_provider.py - Detect and configure AI providers for AI Skills.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

try:
    from env_loader import load_env
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from env_loader import load_env

from model_registry import PROVIDERS, LOCAL_PROVIDERS, get_registry

SUPPORTED = list(PROVIDERS)

PROVIDER_METADATA = {
    "claude": {
        "display_name": "Claude Code",
        "env_keys": ["ANTHROPIC_API_KEY"],
        "base_url_keys": ["ANTHROPIC_BASE_URL", "CLAUDE_BASE_URL"],
        "model_keys": ["AI_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL"],
        "cli_tool": "claude",
        "session_dir": Path.home() / ".claude" / "projects",
        "default_base_url": "https://api.anthropic.com",
        "test_path": "/v1/models",
    },
    "gemini": {
        "display_name": "Gemini CLI",
        "env_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "base_url_keys": ["GEMINI_BASE_URL", "GOOGLE_BASE_URL"],
        "model_keys": ["AI_MODEL", "GEMINI_MODEL", "GOOGLE_MODEL"],
        "cli_tool": "gemini",
        "session_dir": Path.home() / ".gemini",
        "default_base_url": "https://generativelanguage.googleapis.com",
        "test_path": "/v1beta/models",
    },
    "openai": {
        "display_name": "OpenAI",
        "env_keys": ["OPENAI_API_KEY"],
        "base_url_keys": ["OPENAI_BASE_URL"],
        "model_keys": ["AI_MODEL", "OPENAI_MODEL"],
        "cli_tool": "openai",
        "session_dir": None,
        "default_base_url": "https://api.openai.com/v1",
        "test_path": "/models",
    },
    "ollama": {
        "display_name": "Ollama",
        "env_keys": [],
        "base_url_keys": ["OLLAMA_BASE_URL", "AI_BASE_URL"],
        "model_keys": ["AI_MODEL", "OLLAMA_MODEL"],
        "cli_tool": "ollama",
        "session_dir": None,
        "default_base_url": "http://localhost:11434",
        "test_path": "/api/tags",
    },
    "mistral": {
        "display_name": "Mistral",
        "env_keys": ["MISTRAL_API_KEY"],
        "base_url_keys": ["MISTRAL_BASE_URL"],
        "model_keys": ["AI_MODEL", "MISTRAL_MODEL"],
        "cli_tool": "mistral",
        "session_dir": None,
        "default_base_url": "https://api.mistral.ai/v1",
        "test_path": "/models",
    },
    "lmstudio": {
        "display_name": "LM Studio",
        "env_keys": [],
        "base_url_keys": ["LMSTUDIO_BASE_URL", "AI_BASE_URL"],
        "model_keys": ["AI_MODEL", "LMSTUDIO_MODEL"],
        "cli_tool": "lms",
        "session_dir": None,
        "default_base_url": "http://localhost:1234/v1",
        "test_path": "/models",
    },
}

def normalize_provider(provider: str | None) -> str:
    value = (provider or "").strip().lower()
    return value if value in SUPPORTED else "unknown"


def list_supported() -> list[str]:
    return list(SUPPORTED)


def get_known_models(provider: str) -> list[str]:
    return get_registry().names(provider)


def detect() -> str:
    load_env()

    provider = normalize_provider(os.environ.get("AI_PROVIDER"))
    if provider != "unknown":
        return provider

    if os.environ.get("ANTHROPIC_API_KEY") or any(key.startswith("CLAUDE_") for key in os.environ):
        return "claude"
    if (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or any(key.startswith("GOOGLE_") for key in os.environ)
    ):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistral"

    model = os.environ.get('AI_MODEL', 'unknown')
    if model != "unknown":
        inferred = get_registry().infer_provider(model)
        if inferred != 'unknown':
            return inferred

    if (Path.home() / ".claude").exists():
        return "claude"
    if (Path.home() / ".gemini").exists():
        return "gemini"

    base_url = os.environ.get("AI_BASE_URL", "").lower()
    if "11434" in base_url or "ollama" in base_url:
        return "ollama"
    if "1234" in base_url or "lmstudio" in base_url:
        return "lmstudio"

    return "unknown"


def get_model(provider: str | None = None) -> str:
    load_env()
    provider = normalize_provider(provider) if provider else detect()

    keys = ["AI_MODEL"]
    if provider in PROVIDER_METADATA:
        keys = PROVIDER_METADATA[provider]["model_keys"]

    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return "unknown"


def get_api_key(provider: str | None = None) -> str | None:
    load_env()
    provider = normalize_provider(provider) if provider else detect()
    for key in PROVIDER_METADATA.get(provider, {}).get("env_keys", []):
        value = os.environ.get(key)
        if value:
            return value
    return None


def get_base_url_env_key(provider: str | None = None) -> str | None:
    provider = normalize_provider(provider) if provider else detect()
    keys = PROVIDER_METADATA.get(provider, {}).get("base_url_keys", [])
    return keys[0] if keys else None


def get_base_url(provider: str | None = None) -> str | None:
    load_env()
    provider = normalize_provider(provider) if provider else detect()
    for key in PROVIDER_METADATA.get(provider, {}).get("base_url_keys", []):
        value = os.environ.get(key)
        if value:
            return value
    if provider == "unknown":
        return os.environ.get("AI_BASE_URL")
    return PROVIDER_METADATA.get(provider, {}).get("default_base_url")


def get_context_limit(model: str | None = None, provider: str | None = None) -> int:
    if model is None:
        selected = provider or detect()
        provider = selected if selected != 'unknown' else None
        model = get_model(provider)
    row = get_registry().resolve(model, provider)
    return row['context_window'] if row else 0


def get_context_table() -> dict[str, int]:
    rows = get_registry().list_models()
    counts = {}
    for row in rows:
        key = row['id'].casefold()
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted((row['id'] if counts[row['id'].casefold()] == 1 else f"{row['provider']}/{row['id']}",
                        row['context_window']) for row in rows))


def get_session_dir(provider: str | None = None) -> Path | None:
    provider = normalize_provider(provider) if provider else detect()
    session_dir = PROVIDER_METADATA.get(provider, {}).get("session_dir")
    if not session_dir:
        return None
    return session_dir if session_dir.exists() else None


def get_data_dir() -> Path:
    from env_loader import get_data_dir as scoped_data_dir
    return scoped_data_dir()


def get_provider_details(provider: str | None = None) -> dict[str, object]:
    provider = normalize_provider(provider) if provider else detect()
    if provider == "unknown":
        return {
            "provider": "unknown",
            "display_name": "Unknown",
            "model": get_model(),
            "local": False,
            "base_url": get_base_url(provider),
            "session_dir": get_session_dir(provider),
        }
    meta = PROVIDER_METADATA[provider]
    return {
        "provider": provider,
        "display_name": meta["display_name"],
        "model": get_model(provider),
        "local": provider in LOCAL_PROVIDERS,
        "base_url": get_base_url(provider),
        "session_dir": get_session_dir(provider),
        "cli_tool": meta["cli_tool"],
        "env_keys": list(meta["env_keys"]),
        "known_models": get_known_models(provider),
    }


def is_local(provider: str | None = None) -> bool:
    provider = normalize_provider(provider) if provider else detect()
    return provider in LOCAL_PROVIDERS


def get_project_config_path() -> Path:
    return Path.cwd() / ".ai-skills.env"


def get_global_config_path() -> Path:
    return Path.home() / ".ai-skills.env"


def set_provider(
    provider: str,
    model: str | None = None,
    base_url: str | None = None,
    global_config: bool = False,
) -> Path:
    normalized = normalize_provider(provider)
    if normalized == "unknown":
        raise ValueError(f"Unsupported provider: {provider}")

    target = get_global_config_path() if global_config else get_project_config_path()
    updates = {"AI_PROVIDER": normalized}
    if model:
        updates["AI_MODEL"] = model
    if base_url:
        base_url_key = get_base_url_env_key(normalized)
        if base_url_key:
            updates[base_url_key] = base_url
    _write_env_updates(target, updates)

    for key, value in updates.items():
        os.environ[key] = value
    return target


def _write_env_updates(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    seen = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def test_provider(provider: str | None = None, timeout: int = 5) -> dict[str, object]:
    provider = normalize_provider(provider) if provider else detect()
    if provider == "unknown":
        return {"provider": "unknown", "ok": False, "message": "No provider detected"}

    base_url = get_base_url(provider)
    if not base_url:
        return {"provider": provider, "ok": False, "message": "No base URL configured"}

    endpoint = base_url.rstrip("/") + PROVIDER_METADATA[provider]["test_path"]
    headers: dict[str, str] = {}
    api_key = get_api_key(provider)

    if provider == "claude" and api_key:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif provider in {"openai", "mistral"} and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider == "gemini" and api_key:
        headers['x-goog-api-key'] = api_key

    if provider not in LOCAL_PROVIDERS and not api_key:
        return {"provider": provider, "ok": False, "message": "Missing API key"}

    request = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="ignore")
            models_count = _count_models_from_payload(provider, payload)
            return {
                "provider": provider,
                "ok": True,
                "status": response.status,
                "endpoint": endpoint,
                "models_count": models_count,
            }
    except urllib.error.HTTPError as exc:
        return {
            "provider": provider,
            "ok": False,
            "status": exc.code,
            "endpoint": endpoint,
            "message": f"HTTP {exc.code}",
        }
    except Exception as exc:
        return {
            "provider": provider,
            "ok": False,
            "endpoint": endpoint,
            "message": f"{type(exc).__name__}: {exc}",
        }


def _count_models_from_payload(provider: str, payload: str) -> int:
    try:
        data = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        return 0

    if provider == "ollama":
        return len(data.get("models", []))
    return len(data.get("data", [])) or len(data.get("models", []))


if __name__ == "__main__":
    details = get_provider_details()
    print(f"Provider: {details['provider']}")
    print(f"Model:    {details['model']}")
    print(f"Local:    {details['local']}")
    print(f"Session:  {details['session_dir']}")
    print(f"Data dir: {get_data_dir()}")
