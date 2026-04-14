#!/usr/bin/env python3
"""
project_brief.py — Load project context into any AI agent instantly

Usage:
  project_brief.py init          # create BRIEF.md template in current directory
  project_brief.py show          # display current BRIEF.md
  project_brief.py inject        # print formatted context block for AI system prompt
  project_brief.py edit          # open BRIEF.md in $EDITOR
  project_brief.py validate      # check BRIEF.md completeness
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR.parent / "_lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))


BRIEF_FILENAME = "BRIEF.md"

BRIEF_TEMPLATE = """\
# Project Brief: {project_name}

## Stack
- Backend:
- Frontend:
- Database:
- Infrastructure:

## Domain Glossary
<!-- Key terms, Thai/English translations, domain-specific concepts -->
-

## Conventions
<!-- Coding standards, naming rules, money format, status values, etc. -->
-

## Key Files
<!-- Important entry points, models, routes, tests -->
-

## Out of Scope
<!-- What the AI should NOT change or touch -->
-
"""

REQUIRED_SECTIONS = ["## Stack", "## Domain Glossary", "## Conventions", "## Key Files"]


def find_brief() -> Path | None:
    """Search current dir and parents for BRIEF.md."""
    current = Path.cwd()
    for directory in [current] + list(current.parents):
        candidate = directory / BRIEF_FILENAME
        if candidate.exists():
            return candidate
        # Stop at git root
        if (directory / ".git").exists():
            break
    return None


def get_brief_path() -> Path:
    """Return the BRIEF.md path to use (existing or new in cwd)."""
    existing = find_brief()
    return existing if existing else Path.cwd() / BRIEF_FILENAME


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    path = Path.cwd() / BRIEF_FILENAME
    if path.exists():
        print(f"BRIEF.md already exists at {path}")
        print("Use 'project-brief edit' to modify it.")
        return

    project_name = Path.cwd().name
    content = BRIEF_TEMPLATE.format(project_name=project_name)
    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")
    print("Edit it to describe your project, then run 'project-brief inject' to use it.")


def cmd_show(args):
    path = find_brief()
    if path is None:
        print("No BRIEF.md found. Run 'project-brief init' to create one.", file=sys.stderr)
        sys.exit(1)
    print(f"# {path}\n")
    print(path.read_text(encoding="utf-8"))


def cmd_inject(args):
    """Print a formatted context block suitable for pasting into an AI system prompt."""
    path = find_brief()
    if path is None:
        print("No BRIEF.md found. Run 'project-brief init' to create one.", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8").strip()
    print("<!-- PROJECT CONTEXT — paste into AI system prompt -->")
    print()
    print(content)
    print()
    print("<!-- END PROJECT CONTEXT -->")


def cmd_edit(args):
    path = find_brief()
    if path is None:
        print("No BRIEF.md found. Run 'project-brief init' first.", file=sys.stderr)
        sys.exit(1)

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad" if os.name == "nt" else "nano"))
    subprocess.run([editor, str(path)])


def cmd_validate(args):
    path = find_brief()
    if path is None:
        print("❌ No BRIEF.md found. Run 'project-brief init' to create one.", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    issues = []
    warnings = []

    # Check required sections exist
    for section in REQUIRED_SECTIONS:
        if section not in content:
            issues.append(f"Missing required section: {section}")

    # Check sections aren't empty (only have placeholder content)
    lines = content.splitlines()
    current_section = None
    section_content: dict[str, list[str]] = {}
    for line in lines:
        if line.startswith("## "):
            current_section = line
            section_content[current_section] = []
        elif current_section:
            stripped = line.strip()
            if stripped and not stripped.startswith("<!--") and stripped != "-":
                section_content[current_section].append(stripped)

    for section in REQUIRED_SECTIONS:
        if section in section_content and not section_content[section]:
            warnings.append(f"Section '{section}' appears empty — fill it in for better AI context")

    # Check title
    first_line = lines[0].strip() if lines else ""
    if not first_line.startswith("# "):
        issues.append("Missing project title (first line should be '# Project Brief: ...')")

    if issues:
        for issue in issues:
            print(f"❌ {issue}")
    if warnings:
        for warning in warnings:
            print(f"⚠️  {warning}")
    if not issues and not warnings:
        print(f"✅ BRIEF.md looks good ({path})")
    elif not issues:
        print(f"\n✅ No errors — but consider filling in the warnings above.")
        sys.exit(0)
    else:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Load project context into any AI agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create BRIEF.md template in current directory")
    sub.add_parser("show", help="Display the current BRIEF.md")
    sub.add_parser("inject", help="Print context block for AI system prompt")
    sub.add_parser("edit", help="Open BRIEF.md in $EDITOR")
    sub.add_parser("validate", help="Check BRIEF.md completeness")

    args = parser.parse_args()
    {
        "init": cmd_init,
        "show": cmd_show,
        "inject": cmd_inject,
        "edit": cmd_edit,
        "validate": cmd_validate,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
