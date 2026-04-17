# Contributing to cortex-skills

Thank you for your interest in contributing! This guide covers how to add new skills, fix bugs, and run the test suite.

## Getting Started

```bash
git clone https://github.com/your-username/cortex-skills
cd cortex-skills
pip install pytest   # only test dependency
pytest tests/ -v
```

## Project Structure

```
cortex-skills/
├── _lib/              # Shared Python utilities (imported by all skills)
│   ├── env_loader.py  # Config loading from ~/.ai-skills.env
│   ├── ai_provider.py # Provider detection
│   └── logger.py      # ANSI-colored terminal output
├── _templates/        # Scaffolding templates
├── <skill-name>/
│   ├── SKILL.md       # Documentation + frontmatter
│   ├── scripts/       # Python or bash implementation
│   │   └── main.py
│   └── <skill-name>   # Shell wrapper (executable, no extension)
├── tests/             # Integration tests
└── install.sh         # Interactive installer
```

## Creating a New Skill

Use the scaffold command:

```bash
python3 skill-creator/scripts/skill_creator.py new my-skill --description "What it does"
# Bash-only:
python3 skill-creator/scripts/skill_creator.py new my-skill --bash
```

This creates:
- `my-skill/SKILL.md` — fill in "When to Use" and "Usage" sections
- `my-skill/scripts/main.py` — implement your commands
- `my-skill/my-skill` — shell wrapper (ready to use)

### Required: SKILL.md frontmatter

```yaml
---
name: my-skill
description: One-line description
providers: claude, gemini, openai, ollama, generic
---
```

### Required: `_lib` path setup

Every `scripts/*.py` must include:

```python
_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR.parent / "_lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
```

### Required: UTF-8 on Windows

Add at the top of any script that outputs emoji or non-ASCII text:

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
```

### Data storage

Use `AI_SKILLS_DATA_DIR` for all persistent data:

```python
from env_loader import get_data_dir

def get_data_file() -> Path:
    return get_data_dir() / "my-skill.jsonl"
```

Default: `~/.ai-skills-data/my-skill.jsonl`

## Writing Tests

Tests live in `tests/`. Use the `data_dir` fixture for isolated temp storage:

```python
def test_something(data_dir):
    # data_dir is a tmp_path with AI_SKILLS_DATA_DIR set
    ...
```

Module reimport pattern (needed when env changes between tests):

```python
def _get_module(data_dir):
    import env_loader
    env_loader._loaded = False
    if "my_module" in sys.modules:
        del sys.modules["my_module"]
    import my_module
    return my_module
```

Run tests:

```bash
pytest tests/ -v
pytest tests/test_todo.py -v    # single file
```

## Validating a Skill

```bash
python3 skill-creator/scripts/skill_creator.py validate my-skill
```

Checks:
- `SKILL.md` exists with `## When to Use` and `## Usage` sections
- Frontmatter present
- Implementation in `scripts/`
- Shell wrapper present

## Code Style

- Python 3.11+ features are fine
- No external dependencies beyond the standard library (no pip installs required)
- Keep scripts self-contained; import from `_lib` only
- Line length: soft limit 120 chars
- Use `ruff check` locally: `pip install ruff && ruff check _lib/`

## Pull Request Checklist

- [ ] New skill has `SKILL.md` with frontmatter, "When to Use", and "Usage"
- [ ] Tests added in `tests/test_<skill-name>.py`
- [ ] `pytest tests/ -v` passes locally
- [ ] Shell wrapper is executable (the CI validate job checks this)
- [ ] `install.sh` `ALL_SKILLS` list updated if adding a new skill
- [ ] `skills.md` table updated with new row
- [ ] `README.md` skills table updated

## Questions?

Open an issue at [github.com/your-username/cortex-skills/issues](https://github.com/your-username/cortex-skills/issues).
