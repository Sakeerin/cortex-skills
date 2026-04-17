"""Integration tests for daily-report/scripts/daily_report.py"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "daily-report" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_module(data_dir):
    import env_loader
    env_loader._loaded = False
    if "daily_report" in sys.modules:
        del sys.modules["daily_report"]
    import daily_report as dr
    return dr


def _write_todos(data_dir: Path, items: list):
    path = data_dir / "todos.jsonl"
    with open(path, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


def _write_notes(data_dir: Path, items: list):
    path = data_dir / "notes.jsonl"
    with open(path, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


def test_collect_todos_done_today(data_dir):
    today = date.today().isoformat()
    _write_todos(data_dir, [
        {"id": "t1", "title": "Task done today", "checked": True,
         "created_at": today + "T08:00:00+00:00", "updated_at": today + "T12:00:00+00:00"},
        {"id": "t2", "title": "Pending task", "checked": False,
         "created_at": today + "T08:00:00+00:00", "updated_at": today + "T08:00:00+00:00"},
    ])
    dr = _get_module(data_dir)
    done, pending = dr.collect_todos(today)
    assert "Task done today" in done
    assert "Pending task" in pending


def test_collect_notes_today(data_dir):
    today = date.today().isoformat()
    _write_notes(data_dir, [
        {"id": "n1", "content": "Note from today", "done": False, "date": today,
         "created_at": today + "T10:00:00+00:00"},
        {"id": "n2", "content": "Old note", "done": False, "date": "2020-01-01",
         "created_at": "2020-01-01T10:00:00+00:00"},
    ])
    dr = _get_module(data_dir)
    notes = dr.collect_notes(today)
    assert "Note from today" in notes
    assert "Old note" not in notes


def test_render_slack_format(data_dir):
    dr = _get_module(data_dir)
    output = dr.render_slack(
        "2026-04-16",
        done=["Fix bug", "Write tests"],
        pending=["Deploy"],
        commits=["feat: add feature (abc123)"],
        notes=["Remember to check X"],
        cost=1.50, tokens=500000, model="claude/claude-sonnet-4-6",
    )
    assert "*Daily Report*" in output or "Daily Report" in output
    assert "Fix bug" in output
    assert "Deploy" in output
    assert "abc123" in output
    assert "500,000" in output


def test_render_markdown_format(data_dir):
    dr = _get_module(data_dir)
    output = dr.render_markdown(
        "2026-04-16", done=["Task A"], pending=[], commits=[], notes=[],
        cost=0.0, tokens=0, model="",
    )
    assert "# Daily Report" in output
    assert "## ✅ Done" in output
    assert "Task A" in output


def test_full_report_no_data(data_dir, capsys):
    dr = _get_module(data_dir)
    old_argv = sys.argv
    sys.argv = ["daily-report"]
    try:
        dr.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
    out = capsys.readouterr().out
    assert "Daily Report" in out
