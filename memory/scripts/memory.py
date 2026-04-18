#!/usr/bin/env python3
"""
memory.py — Persistent memory across sessions and providers

Usage:
  memory.py add KEY VALUE [--tag TAG]
  memory.py list [--tag TAG]
  memory.py get KEY
  memory.py search KEYWORD
  memory.py delete KEY
  memory.py context
  memory.py export
  memory.py clear
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
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


def get_memory_file() -> Path:
    return get_data_dir() / "memory.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_memory() -> dict:
    """Load memory keyed by `key` (last write wins)."""
    path = get_memory_file()
    if not path.exists():
        return {}
    entries = {}
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
            key = obj.get("key")
            if not key:
                continue
            if obj.get("deleted"):
                entries.pop(key, None)
            else:
                entries[key] = {**entries.get(key, {}), **obj}
    return entries


def append_event(event: dict) -> None:
    path = get_memory_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args):
    entries = load_memory()
    key = args.key
    is_update = key in entries
    ts = now_iso()
    event = {
        "id": entries[key].get("id", str(uuid.uuid4())) if is_update else str(uuid.uuid4()),
        "key": key,
        "value": args.value,
        "tags": args.tag or (entries[key].get("tags") if is_update else []),
        "created_at": entries[key].get("created_at", ts) if is_update else ts,
        "updated_at": ts,
    }
    append_event(event)
    action = "Updated" if is_update else "Saved"
    print(f"{action} memory '{key}'")


def cmd_list(args):
    entries = load_memory()
    items = list(entries.values())

    if args.tag:
        items = [e for e in items if args.tag in (e.get("tags") or [])]

    if not items:
        print("No memory entries found.")
        return

    items.sort(key=lambda e: e["key"])
    for e in items:
        tags = " ".join(f"#{t}" for t in (e.get("tags") or []))
        tags_str = f"  {tags}" if tags else ""
        # Truncate long values
        val = e["value"]
        val_display = val[:80] + "..." if len(val) > 80 else val
        print(f"  {e['key']:<24} {val_display}{tags_str}")


def cmd_get(args):
    entries = load_memory()
    key = args.key
    if key not in entries:
        # Try prefix match
        matches = [k for k in entries if k.startswith(key)]
        if not matches:
            print(f"Memory '{key}' not found.", file=sys.stderr)
            sys.exit(1)
        if len(matches) > 1:
            print(f"Ambiguous key '{key}': {matches}", file=sys.stderr)
            sys.exit(1)
        key = matches[0]
    print(entries[key]["value"])


def cmd_search(args):
    entries = load_memory()
    kw = args.keyword.lower()
    matches = [
        e for e in entries.values()
        if kw in e["key"].lower()
        or kw in e["value"].lower()
        or kw in " ".join(e.get("tags") or []).lower()
    ]
    if not matches:
        print(f"No memory matching '{args.keyword}'.")
        return
    for e in sorted(matches, key=lambda x: x["key"]):
        tags = " ".join(f"#{t}" for t in (e.get("tags") or []))
        tags_str = f"  {tags}" if tags else ""
        val = e["value"]
        val_display = val[:80] + "..." if len(val) > 80 else val
        print(f"  {e['key']:<24} {val_display}{tags_str}")


def cmd_delete(args):
    entries = load_memory()
    key = args.key
    if key not in entries:
        print(f"Memory '{key}' not found.", file=sys.stderr)
        sys.exit(1)
    append_event({"key": key, "deleted": True, "updated_at": now_iso()})
    print(f"Deleted memory '{key}'")


def cmd_context(args):
    """Generate a context block suitable for injecting into an AI system prompt."""
    entries = load_memory()
    if not entries:
        print("No memory entries. Add with: memory add KEY VALUE")
        return

    items = sorted(entries.values(), key=lambda e: e["key"])
    print("## Persistent Memory\n")
    for e in items:
        tags = ", ".join(e.get("tags") or [])
        tag_note = f" _(tags: {tags})_" if tags else ""
        print(f"- **{e['key']}**: {e['value']}{tag_note}")


def cmd_export(args):
    entries = load_memory()
    for e in sorted(entries.values(), key=lambda x: x["key"]):
        print(json.dumps(e, ensure_ascii=False))


def cmd_clear(args):
    entries = load_memory()
    if not entries:
        print("No memory entries to clear.")
        return
    ts = now_iso()
    for key in entries:
        append_event({"key": key, "deleted": True, "updated_at": ts})
    print(f"Cleared {len(entries)} memory entry(s).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Persistent memory across sessions and AI providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Save or update a memory entry")
    p_add.add_argument("key", help="Memory key (e.g. 'user_pref', 'project')")
    p_add.add_argument("value", help="Memory value")
    p_add.add_argument("--tag", action="append", help="Tag (repeatable)")

    p_list = sub.add_parser("list", help="List all memory entries")
    p_list.add_argument("--tag", help="Filter by tag")

    p_get = sub.add_parser("get", help="Get a memory value by key")
    p_get.add_argument("key")

    p_search = sub.add_parser("search", help="Search memory entries")
    p_search.add_argument("keyword")

    p_del = sub.add_parser("delete", help="Delete a memory entry")
    p_del.add_argument("key")

    sub.add_parser("context", help="Generate a context block for AI system prompts")
    sub.add_parser("export", help="Export all memory as JSONL")
    sub.add_parser("clear", help="Delete all memory entries")

    args = parser.parse_args()
    {
        "add": cmd_add, "list": cmd_list, "get": cmd_get,
        "search": cmd_search, "delete": cmd_delete,
        "context": cmd_context, "export": cmd_export, "clear": cmd_clear,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
