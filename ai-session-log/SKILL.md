---
name: ai-session-log
description: Browse, search, and export AI session history across Claude and Gemini
providers: claude, gemini
---

# ai-session-log

> Read and query your AI session history. Supports Claude Code (reads `~/.claude/projects/`) and Gemini CLI (reads `~/.gemini/`).

## When to Use

Activate when the user:
- Asks "what did I work on yesterday?"
- Wants to find a session where they discussed something specific
- Needs to export a session as documentation
- Asks for session usage statistics

## Usage

```bash
python3 ~/.ai-skills/ai-session-log/scripts/ai_session_log.py [options]
# or via wrapper:
ai-session-log [options]
```

### Show recent sessions

```bash
ai-session-log                          # last 3 sessions (all providers)
ai-session-log --latest                 # same
ai-session-log --latest --count 10      # last 10 sessions
ai-session-log --provider claude        # Claude only
ai-session-log --provider gemini        # Gemini only
```

### Search

```bash
ai-session-log --search "payment webhook"
ai-session-log --search "race condition" --provider claude
```

### Export

```bash
ai-session-log --export markdown         # print latest session as Markdown
ai-session-log --export markdown > session.md
```

### Statistics

```bash
ai-session-log --stats                  # aggregate stats across all providers
ai-session-log --stats --provider claude
```

## Session Sources

| Provider | Session Directory | Format |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` | JSONL per session |
| Gemini CLI | `~/.gemini/**/*.jsonl` or `.json` | JSONL per session |
| OpenAI | ❌ Not available | API history not stored locally |
| Ollama | ❌ Not stored | No session persistence |

## Notes

- Requires Python 3.11+
- Read-only — never modifies session files
- Content is truncated to 200 chars per message in summaries (full content in `--export`)
- Session files can be large; `--search` reads all sessions but returns first matches
