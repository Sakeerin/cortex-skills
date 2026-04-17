"""Integration tests for notes/scripts/notes.py"""

import json
import sys
from pathlib import Path
from datetime import date

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notes" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_module(data_dir):
    import env_loader
    env_loader._loaded = False
    if "notes" in sys.modules:
        del sys.modules["notes"]
    import notes as n
    n.get_notes_file = lambda: Path(data_dir) / "notes.jsonl"
    return n


def _run(args, data_dir):
    n = _get_module(data_dir)
    old_argv = sys.argv
    sys.argv = ["notes"] + args
    try:
        n.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


def _load(data_dir):
    n = _get_module(data_dir)
    return n.load_notes()


def test_add_note(data_dir):
    _run(["add", "Test note content", "--tag", "idea"], data_dir)
    notes = _load(data_dir)
    assert len(notes) == 1
    note = list(notes.values())[0]
    assert note["content"] == "Test note content"
    assert "idea" in note["tags"]
    assert note["done"] is False
    assert note["date"] == date.today().isoformat()


def test_done_marks_note(data_dir):
    _run(["add", "Mark done note"], data_dir)
    notes = _load(data_dir)
    nid = list(notes.keys())[0]
    _run(["done", nid[:8]], data_dir)
    notes = _load(data_dir)
    assert notes[nid]["done"] is True


def test_delete_note(data_dir):
    _run(["add", "Delete this note"], data_dir)
    notes = _load(data_dir)
    nid = list(notes.keys())[0]
    _run(["delete", nid[:8]], data_dir)
    notes = _load(data_dir)
    assert len(notes) == 0


def test_export_markdown(data_dir, capsys):
    _run(["add", "Export this"], data_dir)
    _run(["export", "--format", "markdown"], data_dir)
    out = capsys.readouterr().out
    assert "# Notes" in out
    assert "Export this" in out
