"""Integration tests for todo/scripts/tasks.py"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "todo" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _run(args: list, data_dir):
    """Import and run tasks.py commands directly."""
    import importlib
    import env_loader
    env_loader._loaded = False

    # Re-import to pick up new data_dir
    if "tasks" in sys.modules:
        del sys.modules["tasks"]
    import tasks

    parser_args = tasks.main.__code__  # just ensure importable
    import argparse

    # Patch get_tasks_file to use data_dir
    original = tasks.get_tasks_file
    tasks.get_tasks_file = lambda: Path(data_dir) / "todos.jsonl"

    old_argv = sys.argv
    sys.argv = ["tasks"] + args
    try:
        tasks.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
        tasks.get_tasks_file = original


def _load_tasks(data_dir):
    path = Path(data_dir) / "todos.jsonl"
    if not path.exists():
        return {}
    tasks_dict = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            tid = obj.get("id")
            if not tid:
                continue
            if obj.get("deleted"):
                tasks_dict.pop(tid, None)
            else:
                tasks_dict[tid] = {**tasks_dict.get(tid, {}), **obj}
    return tasks_dict


def test_add_task(data_dir, capsys):
    _run(["add", "--title", "Test task", "--priority", "high", "--tag", "backend", "--project", "myapp"], data_dir)
    tasks = _load_tasks(data_dir)
    assert len(tasks) == 1
    task = list(tasks.values())[0]
    assert task["title"] == "Test task"
    assert task["priority"] == "high"
    assert "backend" in task["tags"]
    assert task["project"] == "myapp"
    assert task["checked"] is False


def test_add_default_priority(data_dir):
    _run(["add", "--title", "Default task"], data_dir)
    tasks = _load_tasks(data_dir)
    task = list(tasks.values())[0]
    assert task["priority"] == "medium"


def test_done_marks_checked(data_dir):
    _run(["add", "--title", "Complete me"], data_dir)
    tasks = _load_tasks(data_dir)
    tid = list(tasks.keys())[0]
    _run(["done", tid[:8]], data_dir)
    tasks = _load_tasks(data_dir)
    assert tasks[tid]["checked"] is True


def test_delete_removes_task(data_dir):
    _run(["add", "--title", "Delete me"], data_dir)
    tasks = _load_tasks(data_dir)
    tid = list(tasks.keys())[0]
    _run(["delete", tid[:8]], data_dir)
    tasks = _load_tasks(data_dir)
    assert len(tasks) == 0


def test_update_priority(data_dir):
    _run(["add", "--title", "Update me", "--priority", "low"], data_dir)
    tasks = _load_tasks(data_dir)
    tid = list(tasks.keys())[0]
    _run(["update", tid[:8], "--priority", "urgent"], data_dir)
    tasks = _load_tasks(data_dir)
    assert tasks[tid]["priority"] == "urgent"


def test_export_markdown(data_dir, capsys):
    _run(["add", "--title", "Export task", "--project", "proj"], data_dir)
    _run(["export", "--format", "markdown"], data_dir)
    out = capsys.readouterr().out
    assert "# Tasks" in out
    assert "Export task" in out
    assert "proj" in out
