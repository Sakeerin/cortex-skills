#!/usr/bin/env python3
"""
notes.py — Quick note-taking during coding sessions

Usage:
  notes.py add "text" [--tag TAG]
  notes.py list [--all] [--tag TAG]
  notes.py search KEYWORD
  notes.py done ID
  notes.py delete ID
  notes.py export [--format markdown]
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone, date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR.parent / "_lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from env_loader import get_data_dir


def get_notes_file() -> Path:
    return get_data_dir() / "notes.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def today_str() -> str:
    return date.today().isoformat()


def load_notes() -> dict:
    path = get_notes_file()
    if not path.exists():
        return {}
    notes = {}
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
            nid = obj.get("id")
            if not nid:
                continue
            if obj.get("deleted"):
                notes.pop(nid, None)
            else:
                notes[nid] = {**notes.get(nid, {}), **obj}
    return notes


def append_event(event: dict) -> None:
    path = get_notes_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def resolve_id(notes: dict, prefix: str) -> str:
    if not prefix:
        print("Note ID is required.", file=sys.stderr)
        sys.exit(1)
    matches = [k for k in notes if k == prefix or k.startswith(prefix)]
    if not matches:
        print(f"Note not found: {prefix}", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Ambiguous prefix '{prefix}': {[m[:8] for m in matches]}", file=sys.stderr)
        sys.exit(1)
    return matches[0]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args):
    nid = str(uuid.uuid4())
    ts = now_iso()
    event = {
        "id": nid,
        "content": args.text,
        "tags": args.tag or [],
        "done": False,
        "date": today_str(),
        "created_at": ts,
        "updated_at": ts,
    }
    append_event(event)
    tags_str = " ".join(f"#{t}" for t in (args.tag or []))
    print(f"Note added {nid[:8]}: {args.text}" + (f"  {tags_str}" if tags_str else ""))


def cmd_list(args):
    notes = load_notes()
    items = list(notes.values())

    if args.tag:
        items = [n for n in items if args.tag in (n.get("tags") or [])]
    if args.done:
        items = [n for n in items if n.get("done")]
    elif not args.all:
        # Default: today's open notes
        items = [n for n in items if n.get("date") == today_str() and not n.get("done")]

    if not items:
        if args.all:
            print("No notes found.")
        else:
            print(f"No notes for today ({today_str()}). Use --all to see all.")
        return

    items.sort(key=lambda n: n.get("created_at", ""))
    for n in items:
        check = "x" if n.get("done") else " "
        tags = " ".join(f"#{t}" for t in (n.get("tags") or []))
        date_str = f"[{n.get('date', '?')}] " if args.all else ""
        extra = f"  {tags}" if tags else ""
        print(f"[{check}] {n['id'][:8]}  {date_str}{n['content']}{extra}")


def cmd_search(args):
    notes = load_notes()
    keyword = args.keyword.lower()
    matches = [
        n for n in notes.values()
        if keyword in n.get("content", "").lower()
        or keyword in " ".join(n.get("tags") or []).lower()
    ]
    if not matches:
        print(f"No notes matching '{args.keyword}'.")
        return
    matches.sort(key=lambda n: n.get("created_at", ""), reverse=True)
    for n in matches:
        check = "x" if n.get("done") else " "
        tags = " ".join(f"#{t}" for t in (n.get("tags") or []))
        extra = f"  {tags}" if tags else ""
        print(f"[{check}] {n['id'][:8]}  [{n.get('date','?')}] {n['content']}{extra}")


def cmd_done(args):
    notes = load_notes()
    nid = resolve_id(notes, args.id)
    append_event({"id": nid, "done": True, "updated_at": now_iso()})
    print(f"Done ✅ {nid[:8]}: {notes[nid]['content']}")


def cmd_delete(args):
    notes = load_notes()
    nid = resolve_id(notes, args.id)
    append_event({"id": nid, "deleted": True, "updated_at": now_iso()})
    print(f"Deleted {nid[:8]}: {notes[nid]['content']}")


def cmd_export(args):
    notes = load_notes()
    items = list(notes.values())
    items.sort(key=lambda n: (n.get("date", ""), n.get("created_at", "")))

    if args.format == "markdown":
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"# Notes — {today}\n")
        # Group by date
        dates: dict[str, list] = {}
        for n in items:
            d = n.get("date", "unknown")
            dates.setdefault(d, []).append(n)
        for d in sorted(dates.keys(), reverse=True):
            print(f"## {d}\n")
            for n in dates[d]:
                check = "x" if n.get("done") else " "
                tags = " ".join(f"`#{t}`" for t in (n.get("tags") or []))
                extra = f" {tags}" if tags else ""
                print(f"- [{check}] {n['content']}{extra}")
            print()
    else:
        for n in items:
            print(json.dumps(n, ensure_ascii=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quick note-taking for coding sessions")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a note")
    p_add.add_argument("text", help="Note content")
    p_add.add_argument("--tag", action="append", help="Tag (repeatable)")

    p_list = sub.add_parser("list", help="List notes (default: today's open notes)")
    p_list.add_argument("--all", action="store_true", help="Show all notes")
    p_list.add_argument("--done", action="store_true", help="Show completed notes only")
    p_list.add_argument("--tag", help="Filter by tag")

    p_search = sub.add_parser("search", help="Search notes")
    p_search.add_argument("keyword")

    p_done = sub.add_parser("done", help="Mark note as done")
    p_done.add_argument("id", help="Note ID or prefix")

    p_del = sub.add_parser("delete", help="Delete a note")
    p_del.add_argument("id", help="Note ID or prefix")

    p_exp = sub.add_parser("export", help="Export notes")
    p_exp.add_argument("--format", choices=["markdown", "jsonl"], default="markdown")

    args = parser.parse_args()
    {
        "add": cmd_add, "list": cmd_list, "search": cmd_search,
        "done": cmd_done, "delete": cmd_delete, "export": cmd_export,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
