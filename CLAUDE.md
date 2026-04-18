# cortex-skills — Claude Code Integration

This file is auto-loaded by Claude Code. It defines all available skills and how to invoke them.

---

## Skills Reference

All skills are installed at `~/.ai-skills/` (or the directory where this repo is cloned).

```
python3 ~/.ai-skills/<skill>/scripts/<script>.py <command> [options]
```

Or if PATH is configured: `<skill-name> <command>`

---

## Available Skills

### Task Management — `todo`

```bash
python3 ~/.ai-skills/todo/scripts/tasks.py add --title "task" --priority high --tag dev
python3 ~/.ai-skills/todo/scripts/tasks.py list
python3 ~/.ai-skills/todo/scripts/tasks.py list --priority urgent
python3 ~/.ai-skills/todo/scripts/tasks.py done <id>
python3 ~/.ai-skills/todo/scripts/tasks.py update <id> --priority medium
python3 ~/.ai-skills/todo/scripts/tasks.py delete <id>
python3 ~/.ai-skills/todo/scripts/tasks.py export --format markdown
```

- Priorities: `low` | `medium` | `high` | `urgent`
- Data: `~/.ai-skills-data/todos.jsonl`

---

### Notes — `notes`

Quick freeform notes — no priority, no due date.

```bash
python3 ~/.ai-skills/notes/scripts/notes.py add "Remember to deploy"
python3 ~/.ai-skills/notes/scripts/notes.py add "idea" --tag idea
python3 ~/.ai-skills/notes/scripts/notes.py list          # today's notes
python3 ~/.ai-skills/notes/scripts/notes.py list --all
python3 ~/.ai-skills/notes/scripts/notes.py search "keyword"
python3 ~/.ai-skills/notes/scripts/notes.py done <id>
python3 ~/.ai-skills/notes/scripts/notes.py export --format markdown
```

- Data: `~/.ai-skills-data/notes.jsonl`

---

### Persistent Memory — `memory`

Key/value store that persists across sessions and providers.

```bash
python3 ~/.ai-skills/memory/scripts/memory.py add "stack" "Python 3.12, FastAPI"
python3 ~/.ai-skills/memory/scripts/memory.py add "conventions" "snake_case, type hints"
python3 ~/.ai-skills/memory/scripts/memory.py list
python3 ~/.ai-skills/memory/scripts/memory.py get "stack"
python3 ~/.ai-skills/memory/scripts/memory.py search "keyword"
python3 ~/.ai-skills/memory/scripts/memory.py context   # outputs block for system prompt injection
python3 ~/.ai-skills/memory/scripts/memory.py delete "key"
python3 ~/.ai-skills/memory/scripts/memory.py clear
```

> Use `memory context` to inject stored context into your current session.

- Data: `~/.ai-skills-data/memory.jsonl`

---

### Prompt Library — `prompt-lib`

Save and reuse prompt templates with `{{variable}}` substitution.

```bash
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py add "code-review" "Review {{language}} code: {{code}}"
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py list
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py use "code-review" --with "language=Python" --with "code=..."
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py search "review"
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py delete "name"
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py export
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py import prompts.json
```

- Template syntax: `{{variable_name}}`
- Data: `~/.ai-skills-data/prompts.json`

---

### Project Brief — `project-brief`

Inject project context into any AI agent automatically.

```bash
python3 ~/.ai-skills/project-brief/scripts/project_brief.py init     # create BRIEF.md template
python3 ~/.ai-skills/project-brief/scripts/project_brief.py show     # display current brief
python3 ~/.ai-skills/project-brief/scripts/project_brief.py inject   # print context block for injection
python3 ~/.ai-skills/project-brief/scripts/project_brief.py validate # check completeness
python3 ~/.ai-skills/project-brief/scripts/project_brief.py edit     # open in $EDITOR
```

> Run `project-brief inject` at the start of a session to provide project context.

- File: `BRIEF.md` in project root (traverses up to git root)

---

### Git Summary — `git-summary`

Human-readable summary of git changes — useful for writing commit messages.

```bash
python3 ~/.ai-skills/git-summary/scripts/git_summary.py              # unstaged changes
python3 ~/.ai-skills/git-summary/scripts/git_summary.py --staged     # staged changes
python3 ~/.ai-skills/git-summary/scripts/git_summary.py --last 5     # last 5 commits
python3 ~/.ai-skills/git-summary/scripts/git_summary.py --since yesterday
python3 ~/.ai-skills/git-summary/scripts/git_summary.py --branch main
python3 ~/.ai-skills/git-summary/scripts/git_summary.py --format prompt  # AI-ready output
```

---

### Daily Report — `daily-report`

Auto-generate standup from todos, git log, and notes.

```bash
python3 ~/.ai-skills/daily-report/scripts/daily_report.py
python3 ~/.ai-skills/daily-report/scripts/daily_report.py --yesterday
python3 ~/.ai-skills/daily-report/scripts/daily_report.py --date 2026-04-10
python3 ~/.ai-skills/daily-report/scripts/daily_report.py --format slack
python3 ~/.ai-skills/daily-report/scripts/daily_report.py --format markdown
```

---

### Session Log — `ai-session-log`

Browse Claude (and Gemini) session history.

```bash
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py --latest
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py --latest --count 10
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py --search "keyword"
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py --provider claude
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py --export markdown
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py --stats
```

- Claude sessions: `~/.claude/projects/**/*.jsonl`

---

### Git Sync — `sync-git`

```bash
bash ~/.ai-skills/sync-git/scripts/sync.sh
```

- Auto-stash, pull, push with retry
- Exit codes: 0=OK, 1=dirty worktree, 2=conflict, 3=push failed

---

### Env Check — `env-check`

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py
python3 ~/.ai-skills/env-check/scripts/env_check.py --all
python3 ~/.ai-skills/env-check/scripts/env_check.py --fix
```

---

### Skill Creator — `skill-creator`

```bash
python3 ~/.ai-skills/skill-creator/scripts/skill_creator.py new my-skill --description "What it does"
python3 ~/.ai-skills/skill-creator/scripts/skill_creator.py list
python3 ~/.ai-skills/skill-creator/scripts/skill_creator.py validate my-skill
```

---

## Configuration

`~/.ai-skills.env`:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
```

Run `python3 ~/.ai-skills/env-check/scripts/env_check.py --fix` if anything is missing.

---

## Tips for Claude Code

- Run `project-brief inject` to load project context at the start of a session
- Run `memory context` to inject persistent memory into the conversation
- Use `todo export --format markdown` to see all pending tasks
- Use `git-summary --staged --format prompt` before writing a commit message
- Use `daily-report` to get a summary of what was done today
