---
name: skill-creator
description: Guide for creating a new AI skill in this repo
providers: claude, gemini, openai, ollama, generic
---

# skill-creator

> Step-by-step guide for creating a new multi-provider AI skill.

## When to Use

Activate when the user says:
- "create a new skill"
- "add a skill called X"
- "make a skill for Y"

---

## Skill Structure

Every skill lives in its own directory at the repo root:

```
<skill-name>/
├── SKILL.md              # Documentation (required)
├── <skill-name>          # Shell wrapper (chmod +x)
└── scripts/
    └── main.py           # Python entry point
```

For bash-only skills (like sync-git), replace `main.py` with a `.sh` script.

---

## Step 1 — Create the directory

```bash
mkdir -p <skill-name>/scripts
```

## Step 2 — Copy the template

```bash
cp _templates/SKILL.md.template <skill-name>/SKILL.md
cp _templates/main.py.template  <skill-name>/scripts/main.py
```

Fill in all `{{PLACEHOLDER}}` values in both files.

## Step 3 — Implement `scripts/main.py`

The template already includes:
- `sys.path` insert so `_lib` is importable without pip
- `argparse` skeleton with subcommands
- Imports for `env_loader`, `logger`

**Key pattern for `_lib` import:**
```python
_SKILL_DIR = Path(__file__).resolve().parent.parent   # scripts/ -> skill-dir/
_LIB_DIR = _SKILL_DIR.parent / "_lib"                 # skill-dir/ -> repo-root/ -> _lib/
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
```

**Reading env config:**
```python
from env_loader import get, get_data_dir
data_file = get_data_dir() / "my-skill.jsonl"
my_setting = get("MY_SETTING", "default-value")
```

**Logging:**
```python
from logger import info, success, warning, error
info("Processing...")
success("Done!")
error("Something went wrong")
```

## Step 4 — Create the shell wrapper

```bash
cat > <skill-name>/<skill-name> << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SKILL_DIR/scripts/main.py" "$@"
EOF
chmod +x <skill-name>/<skill-name>
```

## Step 5 — Update SKILL.md

Fill in:
- `name`, `description`, `providers` frontmatter
- When to Use section (trigger phrases)
- All commands with examples
- Data section (what file, what schema)

## Step 6 — Test

```bash
# Direct Python
python3 <skill-name>/scripts/main.py --help
python3 <skill-name>/scripts/main.py <command>

# Via wrapper (from skill directory or if in PATH)
./<skill-name>/<skill-name> --help
```

## Step 7 — Update skills.md

Add your new skill to the table at the repo root [skills.md](../skills.md).

---

## Data Storage Convention

- Store all data in `get_data_dir() / "<skill-name>.jsonl"` (or `.json` if not append-only)
- Use JSONL for append-only logs (event sourcing)
- Use JSON for config/settings files
- Never hardcode paths — always use `get_data_dir()`

## Naming Conventions

| Item | Convention | Example |
|---|---|---|
| Skill directory | kebab-case | `my-skill/` |
| Python file | snake_case | `my_skill.py` |
| Shell wrapper | same as skill dir | `my-skill/my-skill` |
| Data file | kebab-case | `my-skill.jsonl` |
| Env vars | UPPER_SNAKE | `MY_SKILL_SETTING` |

## Provider Compatibility

Mark your skill's provider support in `skills.md`:
- ✅ Full support
- ⚠️ Partial / requires manual config
- ❌ Not applicable

If your skill reads AI session files, add provider-specific adapter code or mark unsupported providers as ❌.
