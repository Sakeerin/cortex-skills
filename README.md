# cortex-skills

> Universal skill collection for AI Code Agents — Claude Code, Gemini CLI, ChatGPT, Ollama, and any AI agent.

Provider-agnostic tools for developer workflows: task management, git sync, cost tracking, prompt library, persistent memory, and more.

---

## Quick Start

### 1. Install a skill

```bash
# Install a single skill via degit (no git clone needed)
npx degit your-username/cortex-skills/todo ~/.ai-skills/todo

# Or clone the full repo
git clone https://github.com/your-username/cortex-skills ~/.ai-skills
```

### 2. Configure your provider

```bash
cat >> ~/.ai-skills.env << 'EOF'
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

### 3. Verify setup

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --fix
```

### 4. (Optional) Add skills to PATH

```bash
# Add all skill wrappers to PATH
for d in ~/.ai-skills/*/; do export PATH="$d:$PATH"; done

# Or add to ~/.bashrc / ~/.zshrc permanently
echo 'for d in ~/.ai-skills/*/; do export PATH="$d:$PATH"; done' >> ~/.zshrc
```

---

## Skills (Phase 1)

| Skill | Description | Invoke |
|---|---|---|
| `time` | Current date and time | `date` |
| `todo` | Task management with priority, tags, projects | `python3 todo/scripts/tasks.py` |
| `sync-git` | Git sync — pull, auto-commit, push | `bash sync-git/scripts/sync.sh` |
| `env-check` | Verify API keys and connectivity | `python3 env-check/scripts/env_check.py` |
| `skill-creator` | Guide for creating new skills | See `skill-creator/SKILL.md` |

See [skills.md](skills.md) for the full list including upcoming phases.

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
ai-skills/
├── _lib/               # Shared Python utilities (env_loader, ai_provider, logger)
├── _templates/         # Boilerplate for new skills
├── time/               # Skill: current date/time
├── todo/               # Skill: task management
├── sync-git/           # Skill: git sync
├── env-check/          # Skill: check API keys & connectivity
├── skill-creator/      # Guide: create new skills
└── skills.md           # Full skill catalog
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

## Data Storage

All skill data is stored at `~/.ai-skills-data/` (configurable via `AI_SKILLS_DATA_DIR`):

```
~/.ai-skills-data/
├── todos.jsonl         # todo tasks
├── notes.jsonl         # notes (Phase 3)
├── memory.jsonl        # persistent memory (Phase 3)
├── prompts.json        # prompt library (Phase 3)
└── cost-log.jsonl      # AI cost tracking (Phase 2)
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

## Roadmap

| Phase | Status | Focus |
|---|---|---|
| 1 — Foundation | ✅ Done | `_lib`, `time`, `todo`, `sync-git`, `env-check` |
| 2 — AI Provider Layer | 🔧 Planned | `ai-provider`, `ai-cost`, `ai-context`, `token-budget` |
| 3 — Productivity | 🔧 Planned | `notes`, `prompt-lib`, `memory`, `git-summary`, `project-brief` |
| 4 — Reporting | 🔧 Planned | `daily-report`, `ai-session-log`, `skill-creator` enhanced |
| 5 — Polish | 🔧 Planned | Tests, CI, docs, community release |

<!-- See [ai-skills-development-plan.md](ai-skills-development-plan.md) for the full roadmap. -->

---

## License

MIT
