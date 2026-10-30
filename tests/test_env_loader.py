"""Tests for _lib/env_loader.py"""

import os
import json
import subprocess
import sys
from pathlib import Path

import pytest
import env_loader


def test_get_returns_env_var(monkeypatch):
    monkeypatch.setenv("TEST_KEY_XYZ", "hello")
    env_loader._loaded = False
    assert env_loader.get("TEST_KEY_XYZ") == "hello"


def test_get_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("NO_SUCH_KEY_XYZ", raising=False)
    env_loader._loaded = False
    assert env_loader.get("NO_SUCH_KEY_XYZ", "default_val") == "default_val"


def test_require_raises_when_missing(monkeypatch):
    monkeypatch.delenv("REQUIRED_KEY_XYZ", raising=False)
    env_loader._loaded = False
    with pytest.raises(EnvironmentError, match="REQUIRED_KEY_XYZ"):
        env_loader.require("REQUIRED_KEY_XYZ")


def test_get_data_dir_creates_directory(tmp_path, monkeypatch):
    target = tmp_path / "skills-data"
    monkeypatch.setenv("AI_SKILLS_DATA_DIR", str(target))
    env_loader._loaded = False
    result = env_loader.get_data_dir()
    assert result.exists()
    assert result == target


def test_parse_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".ai-skills.env"
    env_file.write_text("MY_TEST_VAR=test_value\n# comment\nANOTHER=123\n")
    monkeypatch.delenv("MY_TEST_VAR", raising=False)
    monkeypatch.delenv("ANOTHER", raising=False)
    env_loader._loaded = False
    env_loader._parse_env_file(env_file)
    assert os.environ.get("MY_TEST_VAR") == "test_value"
    assert os.environ.get("ANOTHER") == "123"


def test_load_env_reloads_project_env_when_cwd_changes(tmp_path, monkeypatch):
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()
    (project_a / ".ai-skills.env").write_text("AI_PROVIDER=claude\n", encoding="utf-8")
    (project_b / ".ai-skills.env").write_text("AI_PROVIDER=openai\n", encoding="utf-8")

    monkeypatch.delenv("AI_PROVIDER", raising=False)
    env_loader.reload_env()

    monkeypatch.chdir(project_a)
    assert env_loader.get("AI_PROVIDER") == "claude"

    monkeypatch.chdir(project_b)
    assert env_loader.get("AI_PROVIDER") == "openai"


def test_config_precedence_and_fallback(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    project = tmp_path / 'project'
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    monkeypatch.chdir(project)
    key = 'CONFIG_PRECEDENCE_TEST'
    monkeypatch.delenv(key, raising=False)
    env_loader.reload_env()
    (home / '.ai-skills.env').write_text(f'{key}=global\n', encoding='utf-8')
    fallback = project / '.env'
    fallback.write_text(f'{key}=fallback\n', encoding='utf-8')
    local = project / '.ai-skills.env'
    local.write_text(f'{key}=project\n', encoding='utf-8')
    try:
        assert env_loader.get(key) == 'project'
        local.write_text(f'{key}=project-updated\n', encoding='utf-8')
        assert env_loader.get(key) == 'project-updated'
        monkeypatch.setenv(key, 'shell')
        local.unlink()
        assert env_loader.get(key) == 'shell'
        monkeypatch.delenv(key)
        env_loader.reload_env()
        assert env_loader.get(key) == 'fallback'
        fallback.unlink()
        assert env_loader.get(key) == 'global'
    finally:
        env_loader.reload_env()


def test_provider_set_survives_new_process(tmp_path):
    home = tmp_path / 'home'
    project = tmp_path / 'project'
    home.mkdir()
    project.mkdir()
    (home / '.ai-skills.env').write_text('AI_PROVIDER=claude\n', encoding='utf-8')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('AI_', 'CLAUDE_', 'OPENAI_', 'GEMINI_', 'ANTHROPIC_'))}
    env.update(HOME=str(home), USERPROFILE=str(home), AI_SKILLS_DATA_DIR=str(tmp_path / 'data'),
               AI_USAGE_AUTO_IMPORT='0', PYTHONDONTWRITEBYTECODE='1')
    script = Path(__file__).resolve().parents[1] / 'ai-provider/scripts/ai_provider.py'

    def run(*args):
        result = subprocess.run([sys.executable, '-B', str(script), '--json', *args],
                                cwd=project, env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr + result.stdout
        return json.loads(result.stdout)['data']

    assert run('status')['provider'] == 'claude'
    run('set', 'openai')
    assert run('status')['provider'] == 'openai'
    assert (home / '.ai-skills.env').read_text(encoding='utf-8') == 'AI_PROVIDER=claude\n'
