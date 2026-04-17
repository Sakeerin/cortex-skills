"""
conftest.py — Shared pytest fixtures for cortex-skills integration tests
"""

import os
import sys
from pathlib import Path

import pytest

# Add _lib to sys.path so all skills can import it
REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "_lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolate skill data to a temp directory for each test."""
    monkeypatch.setenv("AI_SKILLS_DATA_DIR", str(tmp_path))
    # Reset env_loader cache so it picks up the new env var
    import env_loader
    env_loader._loaded = False
    yield tmp_path
    env_loader._loaded = False


@pytest.fixture
def skill_path():
    """Return a helper to resolve paths to skill scripts."""
    def _path(skill: str, script: str) -> Path:
        return REPO_ROOT / skill / "scripts" / script
    return _path
