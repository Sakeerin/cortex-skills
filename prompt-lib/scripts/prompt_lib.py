#!/usr/bin/env python3
"""
prompt_lib.py — Personal prompt library with template variables

Usage:
  prompt_lib.py add NAME "prompt text" [--description DESC] [--tag TAG]
  prompt_lib.py list [--tag TAG]
  prompt_lib.py search KEYWORD
  prompt_lib.py use NAME [--with KEY=VALUE ...]
  prompt_lib.py edit NAME
  prompt_lib.py delete NAME
  prompt_lib.py export
  prompt_lib.py import FILE
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import os
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

_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def get_prompts_file() -> Path:
    return get_data_dir() / "prompts.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_prompts() -> dict:
    path = get_prompts_file()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prompts(prompts: dict) -> None:
    path = get_prompts_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)


def extract_vars(text: str) -> list[str]:
    return sorted(set(_VAR_PATTERN.findall(text)))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(args):
    prompts = load_prompts()
    name = args.name
    if name in prompts:
        print(f"Prompt '{name}' already exists. Use 'edit' to modify it.", file=sys.stderr)
        sys.exit(1)
    ts = now_iso()
    prompts[name] = {
        "name": name,
        "content": args.text,
        "description": args.description or "",
        "tags": args.tag or [],
        "created_at": ts,
        "updated_at": ts,
    }
    save_prompts(prompts)
    vars_found = extract_vars(args.text)
    vars_str = f"  variables: {vars_found}" if vars_found else ""
    print(f"Added prompt '{name}'{vars_str}")


def cmd_list(args):
    prompts = load_prompts()
    items = list(prompts.values())

    if args.tag:
        items = [p for p in items if args.tag in (p.get("tags") or [])]

    if not items:
        print("No prompts found.")
        return

    items.sort(key=lambda p: p["name"])
    for p in items:
        desc = f"  — {p['description']}" if p.get("description") else ""
        tags = " ".join(f"#{t}" for t in (p.get("tags") or []))
        tags_str = f"  {tags}" if tags else ""
        vars_found = extract_vars(p["content"])
        vars_str = f"  [{', '.join(vars_found)}]" if vars_found else ""
        print(f"  {p['name']}{desc}{tags_str}{vars_str}")


def cmd_search(args):
    prompts = load_prompts()
    kw = args.keyword.lower()
    matches = [
        p for p in prompts.values()
        if kw in p["name"].lower()
        or kw in p.get("description", "").lower()
        or kw in p["content"].lower()
        or kw in " ".join(p.get("tags") or []).lower()
    ]
    if not matches:
        print(f"No prompts matching '{args.keyword}'.")
        return
    for p in sorted(matches, key=lambda x: x["name"]):
        desc = f"  — {p['description']}" if p.get("description") else ""
        print(f"  {p['name']}{desc}")


def cmd_use(args):
    prompts = load_prompts()
    name = args.name
    if name not in prompts:
        print(f"Prompt '{name}' not found. Run 'prompt-lib list' to see available prompts.", file=sys.stderr)
        sys.exit(1)

    content = prompts[name]["content"]
    vars_found = extract_vars(content)

    # Parse --with KEY=VALUE pairs
    substitutions = {}
    for pair in (args.with_ or []):
        if "=" not in pair:
            print(f"Invalid --with value '{pair}'. Use KEY=VALUE format.", file=sys.stderr)
            sys.exit(1)
        k, _, v = pair.partition("=")
        substitutions[k.strip()] = v.strip()

    # Apply substitutions
    result = content
    for var in vars_found:
        if var in substitutions:
            result = result.replace(f"{{{{{var}}}}}", substitutions[var])

    # Warn about unfilled variables
    remaining = extract_vars(result)
    if remaining:
        print(f"⚠️  Unfilled variables: {remaining}", file=sys.stderr)

    print(result)


def cmd_edit(args):
    prompts = load_prompts()
    name = args.name
    if name not in prompts:
        print(f"Prompt '{name}' not found.", file=sys.stderr)
        sys.exit(1)

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad" if os.name == "nt" else "nano"))

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(prompts[name]["content"])
        tmp_path = tmp.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path, "r", encoding="utf-8") as f:
            new_content = f.read()
        prompts[name]["content"] = new_content
        prompts[name]["updated_at"] = now_iso()
        save_prompts(prompts)
        print(f"Updated prompt '{name}'")
    finally:
        os.unlink(tmp_path)


def cmd_delete(args):
    prompts = load_prompts()
    name = args.name
    if name not in prompts:
        print(f"Prompt '{name}' not found.", file=sys.stderr)
        sys.exit(1)
    del prompts[name]
    save_prompts(prompts)
    print(f"Deleted prompt '{name}'")


def cmd_export(args):
    prompts = load_prompts()
    print(json.dumps(prompts, ensure_ascii=False, indent=2))


def cmd_import(args):
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        incoming = json.load(f)

    prompts = load_prompts()
    added, skipped = 0, 0
    for name, data in incoming.items():
        if name in prompts and not args.overwrite:
            skipped += 1
            continue
        prompts[name] = data
        added += 1

    save_prompts(prompts)
    print(f"Imported {added} prompt(s)" + (f", skipped {skipped} (already exist — use --overwrite)" if skipped else ""))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Personal prompt library with template variables")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a prompt")
    p_add.add_argument("name", help="Unique prompt name")
    p_add.add_argument("text", help="Prompt content (use {{variable}} for placeholders)")
    p_add.add_argument("--description", "-d", help="Short description")
    p_add.add_argument("--tag", action="append", help="Tag (repeatable)")

    p_list = sub.add_parser("list", help="List all prompts")
    p_list.add_argument("--tag", help="Filter by tag")

    p_search = sub.add_parser("search", help="Search prompts")
    p_search.add_argument("keyword")

    p_use = sub.add_parser("use", help="Print a prompt (with optional variable substitution)")
    p_use.add_argument("name")
    p_use.add_argument("--with", dest="with_", action="append", metavar="KEY=VALUE",
                        help="Substitute template variable (repeatable)")

    p_edit = sub.add_parser("edit", help="Edit a prompt in $EDITOR")
    p_edit.add_argument("name")

    p_del = sub.add_parser("delete", help="Delete a prompt")
    p_del.add_argument("name")

    sub.add_parser("export", help="Export all prompts as JSON")

    p_import = sub.add_parser("import", help="Import prompts from a JSON file")
    p_import.add_argument("file", help="Path to JSON file")
    p_import.add_argument("--overwrite", action="store_true", help="Overwrite existing prompts")

    args = parser.parse_args()
    {
        "add": cmd_add, "list": cmd_list, "search": cmd_search,
        "use": cmd_use, "edit": cmd_edit, "delete": cmd_delete,
        "export": cmd_export, "import": cmd_import,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
