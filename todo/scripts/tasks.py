#!/usr/bin/env python3
"""
tasks.py — Enhanced JSONL-based task manager for AI Skills

Usage:
  tasks.py list [--priority PRIORITY] [--tag TAG] [--project PROJECT] [--all] [--checked]
  tasks.py add --title TITLE [--priority PRIORITY] [--tag TAG ...] [--project PROJECT] [--due DATE]
  tasks.py update ID [--title TITLE] [--priority PRIORITY] [--tag TAG ...] [--project PROJECT]
                    [--due DATE] [--checked BOOL]
  tasks.py done ID
  tasks.py delete ID
  tasks.py get ID
  tasks.py export --format markdown
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows (handles emoji in priority icons)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Allow importing _lib without pip install
_SKILL_DIR = Path(__file__).resolve().parent.parent   # scripts/ -> todo/
_LIB_DIR = _SKILL_DIR.parent / "_lib"                 # todo/ -> repo-root/ -> _lib/
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from env_loader import get_data_dir

VALID_PRIORITIES = ["low", "medium", "high", "urgent"]
PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_ICONS = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


def get_tasks_file() -> Path:
    return get_data_dir() / "todos.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_tasks() -> dict:
    """Reconstruct current task state from JSONL event log."""
    path = get_tasks_file()
    if not path.exists():
        return {}
    tasks = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: skipping corrupted line in {path.name}", file=sys.stderr)
                continue
            tid = obj.get("id")
            if not tid:
                continue
            if obj.get("deleted"):
                tasks.pop(tid, None)
            else:
                tasks[tid] = {**tasks.get(tid, {}), **obj}
    return tasks


def append_event(event: dict) -> None:
    path = get_tasks_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def resolve_id(tasks: dict, tid_prefix: str) -> str:
    if not tid_prefix:
        print("Task ID is required.", file=sys.stderr)
        sys.exit(1)
    matches = [k for k in tasks if k == tid_prefix or k.startswith(tid_prefix)]
    if not matches:
        print(f"Task not found: {tid_prefix}", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Ambiguous ID prefix '{tid_prefix}', matches: {[m[:8] for m in matches]}", file=sys.stderr)
        sys.exit(1)
    return matches[0]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args):
    tasks = load_tasks()
    items = list(tasks.values())

    # Filters
    if args.priority:
        items = [t for t in items if t.get("priority") == args.priority]
    if args.tag:
        items = [t for t in items if args.tag in (t.get("tags") or [])]
    if args.project:
        items = [t for t in items if t.get("project") == args.project]
    if args.checked:
        items = [t for t in items if t.get("checked") is True]
    elif not args.all:
        items = [t for t in items if not t.get("checked")]

    if not items:
        print("No tasks found.")
        return

    items.sort(key=lambda t: (
        PRIORITY_ORDER.get(t.get("priority", "medium"), 9),
        t.get("due_date") or "9999",
    ))

    for t in items:
        check = "x" if t.get("checked") else " "
        priority = t.get("priority", "medium")
        icon = PRIORITY_ICONS.get(priority, "⚪")
        tags = " ".join(f"#{tag}" for tag in (t.get("tags") or []))
        project = f"[{t['project']}]" if t.get("project") else ""
        due = f"due:{t['due_date']}" if t.get("due_date") else ""
        extras = "  ".join(x for x in [tags, project, due] if x)
        print(f"[{check}] {icon} {t['id'][:8]}  {t['title']}"
              + (f"  {extras}" if extras else ""))


def cmd_add(args):
    tid = str(uuid.uuid4())
    ts = now_iso()
    priority = args.priority or "medium"
    if priority not in VALID_PRIORITIES:
        print(f"Invalid priority '{priority}'. Choose: {VALID_PRIORITIES}", file=sys.stderr)
        sys.exit(1)
    event = {
        "id": tid,
        "title": args.title,
        "checked": False,
        "priority": priority,
        "tags": args.tag or [],
        "project": args.project or None,
        "due_date": args.due or None,
        "created_at": ts,
        "updated_at": ts,
    }
    append_event(event)
    icon = PRIORITY_ICONS.get(priority, "⚪")
    print(f"Added {icon} {tid[:8]}: {args.title}")


def cmd_update(args):
    tasks = load_tasks()
    tid = resolve_id(tasks, args.id)
    event = {"id": tid, "updated_at": now_iso()}

    if args.title:
        event["title"] = args.title
    if args.priority:
        if args.priority not in VALID_PRIORITIES:
            print(f"Invalid priority. Choose: {VALID_PRIORITIES}", file=sys.stderr)
            sys.exit(1)
        event["priority"] = args.priority
    if args.tag is not None:
        event["tags"] = args.tag
    if args.project is not None:
        event["project"] = args.project or None
    if args.due is not None:
        event["due_date"] = args.due or None
    if args.checked is not None:
        event["checked"] = args.checked.lower() in ("true", "1", "yes")

    append_event(event)
    print(f"Updated task {tid[:8]}")


def cmd_done(args):
    tasks = load_tasks()
    tid = resolve_id(tasks, args.id)
    append_event({"id": tid, "checked": True, "updated_at": now_iso()})
    print(f"Done ✅ {tid[:8]}: {tasks[tid]['title']}")


def cmd_delete(args):
    tasks = load_tasks()
    tid = resolve_id(tasks, args.id)
    append_event({"id": tid, "deleted": True, "updated_at": now_iso()})
    print(f"Deleted {tid[:8]}: {tasks[tid]['title']}")


def cmd_get(args):
    tasks = load_tasks()
    tid = resolve_id(tasks, args.id)
    print(json.dumps(tasks[tid], ensure_ascii=False, indent=2))


def cmd_export(args):
    tasks = load_tasks()
    if args.format == "markdown":
        _export_markdown(tasks)
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        sys.exit(1)


def _export_markdown(tasks: dict) -> None:
    items = list(tasks.values())
    items.sort(key=lambda t: (
        PRIORITY_ORDER.get(t.get("priority", "medium"), 9),
        t.get("due_date") or "9999",
    ))

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"# Tasks — {today}\n")

    # Group by project
    projects: dict[str, list] = {}
    for t in items:
        proj = t.get("project") or "(no project)"
        projects.setdefault(proj, []).append(t)

    for proj, proj_tasks in sorted(projects.items()):
        print(f"## {proj}\n")
        for t in proj_tasks:
            check = "x" if t.get("checked") else " "
            tags = " ".join(f"`#{tag}`" for tag in (t.get("tags") or []))
            due = f" _(due {t['due_date']})_" if t.get("due_date") else ""
            extra = f" {tags}" if tags else ""
            print(f"- [{check}] {t['title']}{extra}{due}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Todo task manager (JSONL event-sourced)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--priority", choices=VALID_PRIORITIES)
    p_list.add_argument("--tag", help="Filter by tag")
    p_list.add_argument("--project", help="Filter by project")
    p_list.add_argument("--checked", action="store_true", help="Show only completed tasks")
    p_list.add_argument("--all", action="store_true", help="Show all tasks including completed")

    # add
    p_add = sub.add_parser("add", help="Add a task")
    p_add.add_argument("--title", required=True, help="Task title")
    p_add.add_argument("--priority", choices=VALID_PRIORITIES, default="medium")
    p_add.add_argument("--tag", action="append", dest="tag", help="Tag (repeatable)")
    p_add.add_argument("--project", help="Project name")
    p_add.add_argument("--due", help="Due date (YYYY-MM-DD)")

    # update
    p_upd = sub.add_parser("update", help="Update a task")
    p_upd.add_argument("id", help="Task ID or prefix")
    p_upd.add_argument("--title")
    p_upd.add_argument("--priority", choices=VALID_PRIORITIES)
    p_upd.add_argument("--tag", action="append", dest="tag", help="Replace tags (repeatable)")
    p_upd.add_argument("--project")
    p_upd.add_argument("--due")
    p_upd.add_argument("--checked", help="true/false")

    # done
    p_done = sub.add_parser("done", help="Mark task as done")
    p_done.add_argument("id", help="Task ID or prefix")

    # delete
    p_del = sub.add_parser("delete", help="Delete a task")
    p_del.add_argument("id", help="Task ID or prefix")

    # get
    p_get = sub.add_parser("get", help="Get full task details")
    p_get.add_argument("id", help="Task ID or prefix")

    # export
    p_exp = sub.add_parser("export", help="Export tasks")
    p_exp.add_argument("--format", choices=["markdown"], default="markdown")

    args = parser.parse_args()
    dispatch = {
        "list": cmd_list,
        "add": cmd_add,
        "update": cmd_update,
        "done": cmd_done,
        "delete": cmd_delete,
        "get": cmd_get,
        "export": cmd_export,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
