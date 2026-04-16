---
name: daily-report
description: Auto-generate daily standup report from todo, git log, AI cost, and notes
providers: claude, gemini, openai, ollama, generic
---

# daily-report

> Generate a daily standup report automatically by combining data from your existing skills.
> No manual writing needed — the report is built from real activity data.

## When to Use

Activate when the user:
- Says "generate daily report", "standup report", "what did I do today"
- Wants a summary of the day's work
- Needs to paste a status update to Slack or a team chat

## Usage

```bash
python3 ~/.ai-skills/daily-report/scripts/daily_report.py [options]
# or via wrapper:
daily-report [options]
```

### Options

```bash
daily-report                       # today's report (plain text)
daily-report --yesterday           # yesterday's report
daily-report --date 2026-04-14     # specific date
daily-report --format slack        # Slack-ready format
daily-report --format markdown     # Markdown format
```

### Example Output (Slack format)

```
📅 *Daily Report — 2026-04-14*

✅ *Done:*
• ✅ Fix race condition in reservation number
• ✅ Implement Cloudflare Stream upload endpoint

🔄 *In Progress:*
• 🔄 Omise payment webhook integration
• 🔄 Write API documentation

📝 *Commits:*
• `feat: add stream upload endpoint (a3f8c2)`
• `fix: lockForUpdate on reservation (b1d4e9)`

💰 *AI Usage:* 1,234,500 tokens — $3.70 (claude/claude-sonnet-4-6)

🚧 *Blockers:* ไม่มี
```

## Data Sources

| Source | What it provides |
|---|---|
| `todos.jsonl` | Tasks marked done today + pending tasks |
| `notes.jsonl` | Notes created today (open ones) |
| `git log` | Commits made today in current repo |
| `cost-log.jsonl` | Token usage and cost for today |

All data is local — no API calls.

## Notes

- Requires Python 3.11+ and git (for commit data)
- If no data exists for a source, that section is silently skipped
- "Done" tasks: items with `checked=true` and `updated_at` matching the target date
- "Pending" tasks: open items created on or before the target date (max 5 shown)
- Commits are read from the current git repository only
