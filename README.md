# cortex-skills

> Universal skill collection for AI Code Agents — Claude Code, Gemini CLI, ChatGPT, Ollama, and any AI agent.

Provider-agnostic tools for developer workflows: task management, git sync, cost tracking, prompt library, persistent memory, and more.

---

## Quick Start

```bash
git clone https://github.com/your-username/cortex-skills ~/.ai-skills
bash ~/.ai-skills/install.sh
```

Or manually in 3 steps:

```bash
# 1. Clone
git clone https://github.com/your-username/cortex-skills ~/.ai-skills

# 2. Configure provider
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF

# 3. Verify
python3 ~/.ai-skills/env-check/scripts/env_check.py --fix
```

**Full setup guides:** [SETUP.md](SETUP.md) | [Windows](docs/setup-windows.md) | [Ollama/Local AI](docs/setup-ollama.md) | [Claude Code](CLAUDE.md)

---

## Skills

| Skill | Description | Invoke |
|---|---|---|
| `time` | Current date and time | `date` |
| `todo` | Task management with priority, tags, projects | `todo add --title "Fix bug" --priority high` |
| `sync-git` | Git sync — pull, auto-commit, push | `sync-git` |
| `env-check` | Verify API keys and connectivity | `env-check --fix` |
| `notes` | Capture and search daily notes | `notes add "Remember to deploy"` |
| `prompt-lib` | Personal prompt library with template variables | `prompt-lib use my-prompt --with key=value` |
| `memory` | Persistent key/value memory for AI context | `memory add "stack" "Python + FastAPI"` |
| `git-summary` | Human-readable git diff summaries | `git-summary --staged --format prompt` |
| `project-brief` | Manage `BRIEF.md` project context | `project-brief inject` |
| `daily-report` | Generate daily standup from todos + git + notes | `daily-report` |
| `ai-session-log` | Browse and search Claude/Gemini session history | `ai-session-log --latest --count 5` |
| `skill-creator` | Scaffold and validate new skills | `skill-creator new my-skill` |

See [skills.md](skills.md) for the full catalog with data paths and compatibility matrix.

---

## Usage with AI Agents

### Claude Code

Add to your `CLAUDE.md` or `.claude/CLAUDE.md`:

```markdown
Skills are installed at ~/.ai-skills/.
To use a skill: python3 ~/.ai-skills/<skill>/scripts/main.py <command>
Or if PATH is configured: <skill-name> <command>
See ~/.ai-skills/<skill>/SKILL.md for usage.
```

### Gemini CLI

Add to `GEMINI.md`:

```markdown
Skills are installed at ~/.ai-skills/.
Run: python3 ~/.ai-skills/<skill>/scripts/main.py <command>
```

### Any AI Agent

Run `python3 ~/.ai-skills/project-brief/scripts/main.py inject` *(Phase 3)* to generate a context block you can paste into any system prompt.

---

## Repo Structure

```
cortex-skills/
├── _lib/               # Shared Python utilities (env_loader, ai_provider, logger)
├── _templates/         # Boilerplate for new skills
├── time/               # Skill: current date/time
├── todo/               # Skill: task management
├── sync-git/           # Skill: git sync
├── env-check/          # Skill: check API keys & connectivity
├── notes/              # Skill: daily notes
├── prompt-lib/         # Skill: prompt library
├── memory/             # Skill: persistent memory
├── git-summary/        # Skill: git diff summaries
├── project-brief/      # Skill: project context (BRIEF.md)
├── daily-report/       # Skill: daily standup report
├── ai-session-log/     # Skill: session history browser
├── skill-creator/      # Skill: scaffold new skills
├── tests/              # Integration tests (pytest)
├── install.sh          # Interactive installer
├── skills.md           # Full skill catalog
└── CONTRIBUTING.md     # How to add new skills
```

Each skill follows this structure:
```
<skill-name>/
├── SKILL.md            # Documentation & usage
├── <skill-name>        # Shell wrapper (chmod +x)
└── scripts/
    └── main.py         # Python entry point
```

---

## Demo

```bash
# Run the interactive demo
bash demo.sh
```

Or try skills manually:

```bash
# Track a task
todo add --title "Review PR #42" --priority high --tag dev

# Save a note
notes add "Standup: shipping auth refactor today"

# Remember something for AI context
memory add "stack" "Python 3.12, FastAPI, PostgreSQL"

# Generate AI context block (paste into any system prompt)
project-brief inject

# Daily standup report
daily-report

# Scaffold a new skill
skill-creator new my-skill --description "My custom skill"
```

---

## Data Storage

All skill data is stored at `~/.ai-skills-data/` (configurable via `AI_SKILLS_DATA_DIR`):

```
~/.ai-skills-data/
├── todos.jsonl         # todo tasks
├── notes.jsonl         # notes
├── memory.jsonl        # persistent memory
├── prompts.json        # prompt library
└── cost-log.jsonl      # AI cost tracking
```

Uses append-only **JSONL** format — no database required.

---

## Configuration

`~/.ai-skills.env` (or `.ai-skills.env` in any project directory):

```bash
AI_PROVIDER=claude            # claude | gemini | openai | ollama | mistral | lmstudio
AI_MODEL=claude-sonnet-4-6
AI_API_KEY=...
AI_BASE_URL=...               # For Ollama / self-hosted (e.g. http://localhost:11434)
AI_SKILLS_DATA_DIR=~/.ai-skills-data
```

---

## Requirements

- Python 3.11+
- bash (for shell wrappers and sync-git)
- git (for sync-git)
- No pip install required — `_lib` is imported directly via `sys.path`

---

## License

MIT
