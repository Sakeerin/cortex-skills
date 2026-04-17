"""Tests for _lib/env_loader.py"""

import os
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
