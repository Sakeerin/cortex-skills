#!/usr/bin/env python3
"""
skill_creator.py — Scaffold a new AI skill from templates

Usage:
  skill_creator.py new NAME [--description DESC] [--bash]
  skill_creator.py list
  skill_creator.py validate NAME
"""

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SKILL_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SKILL_DIR.parent
_LIB_DIR = _REPO_ROOT / "_lib"
_TEMPLATES_DIR = _REPO_ROOT / "_templates"

if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

REQUIRED_FILES = ["SKILL.md"]
OPTIONAL_FILES = ["scripts/main.py", "scripts/main.sh"]

# ---------------------------------------------------------------------------
# Scaffolding templates
# ---------------------------------------------------------------------------

_SKILL_MD = """\
---
name: {name}
description: {description}
providers: claude, gemini, openai, ollama, generic
---

# {name}

> {description}

## When to Use

Activate when the user asks to ...

## Usage

```bash
python3 ~/.ai-skills/{name}/scripts/main.py <command>
# or via wrapper:
{name} <command>
```

### Commands

```bash
{name} --help
```

## Data

Stored at `$AI_SKILLS_DATA_DIR/{name}.jsonl` (default: `~/.ai-skills-data/{name}.jsonl`).

## Notes

- Requires Python 3.11+
"""

_MAIN_PY = """\
#!/usr/bin/env python3
\"\"\"
main.py — {description}

Usage:
  main.py <command> [options]
  main.py --help
\"\"\"

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Allow importing _lib without pip install
_SKILL_DIR = Path(__file__).resolve().parent.parent   # scripts/ -> skill-dir/
_LIB_DIR = _SKILL_DIR.parent / "_lib"                 # skill-dir/ -> repo-root/ -> _lib/
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from env_loader import get, get_data_dir
from logger import info, success, warning, error


def get_data_file() -> Path:
    return get_data_dir() / "{name}.jsonl"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_example(args):
    info("Running example command...")
    success("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="{description}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_example = sub.add_parser("example", help="Example command")

    args = parser.parse_args()
    {{"example": cmd_example}}[args.cmd](args)


if __name__ == "__main__":
    main()
"""

_WRAPPER_SH = """\
#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec python3 "$SKILL_DIR/scripts/main.py" "$@"
"""

_WRAPPER_BASH = """\
#!/usr/bin/env bash
# {name} — bash-only skill
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
exec bash "$SKILL_DIR/scripts/main.sh" "$@"
"""

_MAIN_SH = """\
#!/usr/bin/env bash
# {name} — {description}
set -euo pipefail
echo "{name}: not yet implemented"
"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_new(args):
    name = args.name.lower().replace(" ", "-")
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        print(f"Invalid skill name '{name}'. Use lowercase letters, numbers, and hyphens.", file=sys.stderr)
        sys.exit(1)

    skill_dir = _REPO_ROOT / name
    if skill_dir.exists():
        print(f"Skill '{name}' already exists at {skill_dir}", file=sys.stderr)
        sys.exit(1)

    description = args.description or f"{name} skill"
    is_bash = args.bash

    # Escape braces in user-supplied description so .format() won't
    # raise KeyError if description contains literal { } characters.
    safe_desc = description.replace("{", "{{").replace("}", "}}")

    # Create directories
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)

    # SKILL.md
    (skill_dir / "SKILL.md").write_text(
        _SKILL_MD.format(name=name, description=safe_desc), encoding="utf-8"
    )

    if is_bash:
        # Bash skill
        (scripts_dir / "main.sh").write_text(
            _MAIN_SH.format(name=name, description=safe_desc), encoding="utf-8"
        )
        wrapper = skill_dir / name
        wrapper.write_text(
            _WRAPPER_BASH.format(name=name, description=safe_desc), encoding="utf-8"
        )
    else:
        # Python skill
        (scripts_dir / "main.py").write_text(
            _MAIN_PY.format(name=name, description=safe_desc), encoding="utf-8"
        )
        wrapper = skill_dir / name
        wrapper.write_text(_WRAPPER_SH, encoding="utf-8")

    print(f"Created skill '{name}' at {skill_dir}/")
    print(f"\nFiles created:")
    for f in sorted(skill_dir.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(_REPO_ROOT)}")
    print(f"\nNext steps:")
    print(f"  1. Edit {name}/SKILL.md — describe when to use and how")
    print(f"  2. Implement {name}/scripts/main{'.' + ('sh' if is_bash else 'py')}")
    print(f"  3. Add to skills.md table")
    print(f"  4. Test: python3 {name}/scripts/main.py --help")


def cmd_list(args):
    skills = []
    for d in sorted(_REPO_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith("."):
            if (d / "SKILL.md").exists():
                # Check if has implementation
                has_impl = any([
                    (d / "scripts" / "main.py").exists(),
                    (d / "scripts" / "main.sh").exists(),
                    list(d.glob("scripts/*.py")),
                    list(d.glob("scripts/*.sh")),
                ])
                status = "✅" if has_impl else "📄"
                skills.append((d.name, status))

    print(f"Skills in {_REPO_ROOT.name}/ ({len(skills)} total)\n")
    for name, status in skills:
        print(f"  {status}  {name}")
    print(f"\n✅ = has implementation  📄 = SKILL.md only")


def cmd_validate(args):
    name = args.name
    skill_dir = _REPO_ROOT / name
    if not skill_dir.exists():
        print(f"Skill '{name}' not found at {skill_dir}", file=sys.stderr)
        sys.exit(1)

    errors = []
    warnings = []

    # Check SKILL.md
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append("Missing SKILL.md")
    else:
        content = skill_md.read_text(encoding="utf-8")
        for section in ["## When to Use", "## Usage"]:
            if section not in content:
                warnings.append(f"SKILL.md missing section: {section}")
        if "---" not in content[:100]:
            warnings.append("SKILL.md missing frontmatter (--- ... ---)")

    # Check implementation
    scripts = list((skill_dir / "scripts").glob("*.py")) + list((skill_dir / "scripts").glob("*.sh")) \
        if (skill_dir / "scripts").exists() else []
    if not scripts:
        warnings.append("No implementation found in scripts/ (SKILL.md only)")

    # Check wrapper
    wrapper = skill_dir / name
    if not wrapper.exists() and scripts:
        warnings.append(f"Missing shell wrapper: {name}/{name}")

    if errors:
        for e in errors:
            print(f"❌ {e}")
    if warnings:
        for w in warnings:
            print(f"⚠️  {w}")
    if not errors and not warnings:
        print(f"✅ Skill '{name}' looks good")
    elif not errors:
        print(f"\n✅ No errors")
    else:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scaffold and manage AI skills")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="Create a new skill from template")
    p_new.add_argument("name", help="Skill name (kebab-case)")
    p_new.add_argument("--description", "-d", help="Short description")
    p_new.add_argument("--bash", action="store_true", help="Create a bash-only skill (no Python)")

    sub.add_parser("list", help="List all skills in the repo")

    p_val = sub.add_parser("validate", help="Validate a skill's structure")
    p_val.add_argument("name", help="Skill name to validate")

    args = parser.parse_args()
    {"new": cmd_new, "list": cmd_list, "validate": cmd_validate}[args.cmd](args)


if __name__ == "__main__":
    main()
