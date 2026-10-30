"""Tests for _lib/ai_provider.py."""

import ai_provider
import env_loader


def _clear_provider_env(monkeypatch):
    for key in [
        "AI_PROVIDER",
        "AI_MODEL",
        "AI_BASE_URL",
        "OPENAI_BASE_URL",
        "OLLAMA_BASE_URL",
        "LMSTUDIO_BASE_URL",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_BASE_URL",
        "GEMINI_BASE_URL",
        "GOOGLE_BASE_URL",
        "MISTRAL_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)
    env_loader._loaded = False


def test_get_base_url_uses_provider_specific_env(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")

    assert ai_provider.get_base_url("openai") == "https://openai.example/v1"
    assert ai_provider.get_base_url("ollama") == "http://localhost:11434"


def test_get_base_url_does_not_leak_global_local_url_to_remote_provider(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")

    assert ai_provider.get_base_url("openai") == "https://api.openai.com/v1"
    assert ai_provider.get_base_url("claude") == "https://api.anthropic.com"


def test_set_provider_writes_provider_specific_base_url_key(tmp_path, monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.chdir(tmp_path)

    path = ai_provider.set_provider("openai", model="gpt-4o", base_url="https://openai.example/v1")
    contents = path.read_text(encoding="utf-8")

    assert "AI_PROVIDER=openai" in contents
    assert "AI_MODEL=gpt-4o" in contents
    assert "OPENAI_BASE_URL=https://openai.example/v1" in contents
    # Use line-start check to avoid false match on "OPENAI_BASE_URL=" containing "AI_BASE_URL="
    assert not any(line.startswith("AI_BASE_URL=") for line in contents.splitlines())


def test_set_provider_uses_local_provider_specific_key(tmp_path, monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.chdir(tmp_path)

    path = ai_provider.set_provider("ollama", base_url="http://127.0.0.1:11434")
    contents = path.read_text(encoding="utf-8")

    assert "OLLAMA_BASE_URL=http://127.0.0.1:11434" in contents
    assert "AI_BASE_URL=" not in contents
