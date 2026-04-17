"""Integration tests for memory/scripts/memory.py"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "memory" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_memory_module(data_dir):
    import env_loader
    env_loader._loaded = False
    if "memory" in sys.modules:
        del sys.modules["memory"]
    import memory as m
    m.get_memory_file = lambda: Path(data_dir) / "memory.jsonl"
    return m


def _run_cmd(args, data_dir):
    m = _get_memory_module(data_dir)
    old_argv = sys.argv
    sys.argv = ["memory"] + args
    try:
        m.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


def _load(data_dir):
    if "memory" in sys.modules:
        del sys.modules["memory"]
    import memory as m
    m.get_memory_file = lambda: Path(data_dir) / "memory.jsonl"
    return m.load_memory()


def test_add_and_get(data_dir, capsys):
    _run_cmd(["add", "mykey", "myvalue"], data_dir)
    entries = _load(data_dir)
    assert "mykey" in entries
    assert entries["mykey"]["value"] == "myvalue"


def test_add_with_tag(data_dir):
    _run_cmd(["add", "pref_key", "pref_value", "--tag", "preference"], data_dir)
    entries = _load(data_dir)
    assert "preference" in entries["pref_key"]["tags"]


def test_update_existing_key(data_dir):
    _run_cmd(["add", "upd_key", "original"], data_dir)
    _run_cmd(["add", "upd_key", "updated"], data_dir)
    entries = _load(data_dir)
    assert entries["upd_key"]["value"] == "updated"


def test_delete(data_dir):
    _run_cmd(["add", "del_key", "delete_me"], data_dir)
    _run_cmd(["delete", "del_key"], data_dir)
    entries = _load(data_dir)
    assert "del_key" not in entries


def test_clear(data_dir):
    _run_cmd(["add", "k1", "v1"], data_dir)
    _run_cmd(["add", "k2", "v2"], data_dir)
    _run_cmd(["clear"], data_dir)
    entries = _load(data_dir)
    assert len(entries) == 0


def test_context_output(data_dir, capsys):
    _run_cmd(["add", "project", "LMS Laravel"], data_dir)
    _run_cmd(["context"], data_dir)
    out = capsys.readouterr().out
    assert "## Persistent Memory" in out
    assert "project" in out
    assert "LMS Laravel" in out
