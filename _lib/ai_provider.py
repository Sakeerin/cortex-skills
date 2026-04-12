#!/usr/bin/env python3
"""
ai_provider.py — Detect and configure AI provider

Detection priority:
  1. AI_PROVIDER env var
  2. Provider-specific env vars (CLAUDE_*, GOOGLE_*, OPENAI_*)
  3. Session directory presence (~/.claude/, ~/.gemini/)
  4. Default: "unknown"
"""

import os
from pathlib import Path

try:
    from env_loader import load_env, get
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from env_loader import load_env, get

SUPPORTED = ["claude", "gemini", "openai", "ollama", "mistral", "lmstudio"]

LOCAL_PROVIDERS = {"ollama", "lmstudio"}

_CONTEXT_LIMITS = {
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5": 200_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gemini-1.5-pro": 1_000_000,
    "llama3.3": 128_000,
    "llama3.2": 128_000,
    "codellama": 16_000,
    "mistral-large": 128_000,
    "mistral-small": 32_000,
}


def detect() -> str:
    """Detect active AI provider. Returns provider name or 'unknown'."""
    load_env()

    # 1. Explicit env var
    provider = os.environ.get("AI_PROVIDER", "").lower()
    if provider in SUPPORTED:
        return provider

    # 2. Provider-specific env vars
    if os.environ.get("ANTHROPIC_API_KEY") or any(
        k.startswith("CLAUDE_") for k in os.environ
    ):
        return "claude"
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or any(
        k.startswith("GOOGLE_") for k in os.environ
    ):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistral"

    # 3. Session directory presence
    if (Path.home() / ".claude").exists():
        return "claude"
    if (Path.home() / ".gemini").exists():
        return "gemini"

    return "unknown"


def get_model() -> str:
    """Get current model name from env."""
    load_env()
    return os.environ.get("AI_MODEL", "unknown")


def get_context_limit(model: str = None) -> int:
    """Return context window size for model. Returns 0 if unknown."""
    if model is None:
        model = get_model()
    model = model.lower()
    # Exact match first
    if model in _CONTEXT_LIMITS:
        return _CONTEXT_LIMITS[model]
    # Prefix match
    for key, limit in _CONTEXT_LIMITS.items():
        if model.startswith(key) or key.startswith(model.split("-")[0]):
            return limit
    return 0


def get_session_dir() -> Path | None:
    """Return provider session directory if it exists."""
    provider = detect()
    dirs = {
        "claude": Path.home() / ".claude" / "projects",
        "gemini": Path.home() / ".gemini",
    }
    path = dirs.get(provider)
    return path if path and path.exists() else None


def get_data_dir() -> Path:
    """Return AI Skills data directory."""
    load_env()
    raw = os.environ.get("AI_SKILLS_DATA_DIR", str(Path.home() / ".ai-skills-data"))
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_local() -> bool:
    """True for providers that run locally (Ollama, LM Studio)."""
    return detect() in LOCAL_PROVIDERS


if __name__ == "__main__":
    print(f"Provider: {detect()}")
    print(f"Model:    {get_model()}")
    print(f"Local:    {is_local()}")
    print(f"Session:  {get_session_dir()}")
    print(f"Data dir: {get_data_dir()}")
