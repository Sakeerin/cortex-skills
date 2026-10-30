# Architecture Guide

How cortex-skills is designed, why, and how to extend it.

---

## Overview

```
cortex-skills/
├── _lib/          ← Shared utilities (no pip install needed)
├── _templates/    ← Scaffolding for new skills
├── <skill>/       ← Each skill is a self-contained directory
│   ├── SKILL.md
│   ├── <skill>    ← Shell wrapper (chmod +x)
│   └── scripts/
│       └── main.py (or *.py)
└── tests/         ← Integration tests (pytest)
```

---

## Core Design Principles

### 1. Zero pip dependencies

All shared code lives in `_lib/` and is imported via `sys.path.insert`:

```python
_SKILL_DIR = Path(__file__).resolve().parent.parent   # scripts/ → skill-dir/
_LIB_DIR = _SKILL_DIR.parent / "_lib"                 # skill-dir/ → repo-root/ → _lib/
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
```

This means **no `pip install`** is required — copy the directory and it works.

### 2. Event-sourced JSONL storage

Skills that persist data (todo, notes, memory) use an append-only JSONL format:

```
{"id":"abc","title":"Fix bug","priority":"high","created_at":"2026-05-08T10:00:00+07:00"}
{"id":"abc","checked":true,"updated_at":"2026-05-08T14:30:00+07:00"}
{"id":"abc","deleted":true,"updated_at":"2026-05-08T16:00:00+07:00"}
```

**Why append-only?**
- Safe against partial writes (each line is atomic JSON)
- Provides a history of changes for free
- Works well for sync across machines (simple `git pull`)

**Compaction:** `_lib/jsonl_store.py` rewrites the file to only current live records when it exceeds 500 lines. This keeps file sizes bounded.

### 3. Provider-agnostic

No skill imports an AI SDK directly. Provider configuration is done through environment variables read by `_lib/env_loader.py`:

```
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

Skills that need AI (e.g., future summarization skills) use `_lib/ai_provider.py` to detect which SDK to call.

---

## `_lib/` Shared Utilities

| Module | Purpose |
|---|---|
| `env_loader.py` | Load config from `~/.ai-skills.env`, `.ai-skills.env`, `.env` |
| `ai_provider.py` | Detect active AI provider; test connectivity; enumerate known models |
| `logger.py` | ANSI-colored terminal output (`info`, `success`, `warning`, `error`) |
| `jsonl_store.py` | Event-sourced JSONL load/append/compact shared by all data skills |
| `data_scope.py` | Canonical project/session identities and isolated hashed storage namespaces |
| `cli.py` | Invocation-local scope flags, structured result envelopes, and shared exit codes |
| `errors.py` | Domain data-validation errors independent of output formatting |
| `model_registry.py` | Versioned catalog, global user overrides, aliases, context and pricing |
| `system_admin.py` | Offline runtime/skill/data health checks and safe Python route inventory |

`cortex.py` is the shared administrative entrypoint. Existing handlers are routed
inside its common CLI boundary rather than spawning shell commands or emitting
nested JSON. `model-registry.json` contains bundled model metadata;
`cost-rates.json` remains a legacy price-only overlay, followed by global user overrides.
See [registry](model-registry.md) and [central CLI](central-cli.md) for schemas and routing.

Scope context uses `ContextVar` and is reset after every CLI invocation, including
failures, so in-process callers cannot inherit the preceding command's scope.
Both data-directory entry points delegate to `env_loader.get_data_dir()`.
See [CLI contract](cli-contract.md) for storage layout and compatibility guarantees.

### `env_loader.py`

Config loading cascades:
```
~/.ai-skills.env   → global defaults
.ai-skills.env     → project override
.env               → fallback
```

Each source only sets variables that aren't already in `os.environ` (shell env wins). Later files don't override earlier files.

The loader detects file changes (mtime + size) and reloads automatically, so per-project `.ai-skills.env` files are picked up correctly.

### `jsonl_store.py`

```python
store = JSONLStore(path, id_key="id")
state = store.load()       # dict[id → merged record]
store.append(event)        # append + auto-compact
store.compact()            # rewrite to live state only
```

Used by: `todo`, `notes`, `memory`

Memory uses `id_key="key"` because its records are keyed by a user-readable string, not a UUID.

---

## Skill Structure

Every skill must have:

```
<skill-name>/
├── SKILL.md              ← Required. Frontmatter + docs.
├── <skill-name>          ← Shell wrapper (optional but standard)
└── scripts/
    └── main.py           ← Entry point (or tasks.py, notes.py, etc.)
```

### `SKILL.md` frontmatter

```yaml
---
name: my-skill
description: One-line description
providers: claude, gemini, openai, ollama, generic
---
```

- `providers`: comma-separated list of supported AI providers
- Use `generic` for skills that work with any/all providers

### Shell wrapper pattern

```bash
#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SKILL_DIR/scripts/main.py" "$@"
```

The wrapper passes `$@` (all args) directly to the Python script, so `todo --help` works as expected.

---

## Data Flow

### Reading skill data

```
User calls: todo list
    ↓
tasks.py cmd_list()
    ↓
load_tasks() → JSONLStore.load()
    ↓
Opens todos.jsonl, reads all lines
    ↓
Reconstructs live state (last-write-wins, deleted entries removed)
    ↓
Filters + sorts + prints
```

### Writing skill data

```
User calls: todo add --title "Fix bug"
    ↓
tasks.py cmd_add()
    ↓
Builds event dict with UUID + timestamps
    ↓
append_event() → JSONLStore.append()
    ↓
Writes JSON line to todos.jsonl
    ↓
If file > 500 lines, triggers JSONLStore.compact()
    ↓
Compact rewrites file to live state only (atomic temp file rename)
```

---

## AI Session Log Adapters

`ai-session-log` reads sessions from Claude and Gemini using adapter modules:

```
ai-session-log/
├── scripts/
│   └── ai_session_log.py   ← CLI + dispatch
└── adapters/
    ├── claude_adapter.py   ← Reads ~/.claude/projects/**/*.jsonl
    └── gemini_adapter.py   ← Reads ~/.gemini/**/*.jsonl
```

### Adding a new provider adapter

Create `ai-session-log/adapters/<provider>_adapter.py`:

```python
def list_sessions(limit: int = 50) -> list[dict]:
    """Return list of session dicts with standard fields."""
    return [
        {
            "provider": "my-provider",
            "project": "project-name",
            "start_time": "2026-05-08T10:00:00+07:00",
            "end_time": "2026-05-08T11:00:00+07:00",
            "turns": 12,
            "input_tokens": 50000,
            "output_tokens": 8000,
            "duration": "1h 00m",
            "file": "/path/to/session.jsonl",
            "messages": [{"role": "user", "content": "..."}, ...],
        }
    ]

def search_sessions(keyword: str, limit: int = 10) -> list[dict]:
    """Return sessions where keyword appears in message content."""
    ...
```

Then register in `ai_session_log.py:_get_adapter()`.

---

## Testing Strategy

### Test isolation

Tests use `data_dir` fixture from `conftest.py`:

```python
@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SKILLS_DATA_DIR", str(tmp_path))
    import env_loader
    env_loader._loaded = False
    yield tmp_path
    env_loader._loaded = False
```

This ensures each test gets its own isolated data directory. Skills that call `get_data_dir()` pick up the temp path.

### Module reimport pattern

When tests need to reload a skill module after env changes:

```python
def _get_module():
    if "module_name" in sys.modules:
        del sys.modules["module_name"]
    import module_name
    return module_name
```

This forces re-evaluation of module-level code (like `get_data_dir()` calls).

---

## Adding a New Skill

1. **Scaffold** with skill-creator:
   ```bash
   python3 skill-creator/scripts/skill_creator.py new my-skill --description "What it does"
   ```

2. **Implement** `my-skill/scripts/main.py`:
   - Follow the `_lib` import pattern
   - Use `JSONLStore` if you need persistence
   - Use `argparse` with subcommands
   - Ensure UTF-8 reconfigure at top (for Windows emoji support)

3. **Document** `my-skill/SKILL.md`:
   - Fill in frontmatter
   - Write "When to Use" and "Usage" sections

4. **Test** `tests/test_my_skill.py`:
   - Use `data_dir` fixture for isolation
   - Cover: add, list, delete, error cases

5. **Register** in `skills.md` table and `CLAUDE.md`

6. **Validate** structure:
   ```bash
   python3 skill-creator/scripts/skill_creator.py validate my-skill
   ```

---

## Configuration Cascade

```
shell environment  (highest priority)
    ↑
~/.ai-skills.env   (user global)
    ↑
.ai-skills.env     (project-local)
    ↑
.env               (generic fallback)
    ↑
built-in defaults  (lowest priority)
```

Variables are set only once — first writer wins. Re-running `load_env()` is safe and cached.
