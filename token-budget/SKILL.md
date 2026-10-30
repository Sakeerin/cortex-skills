---
name: token-budget
description: Manage daily, session, and monthly AI cost budgets
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# token-budget

Set and inspect daily, session, and monthly budgets that are backed by the shared cost tracker.

## Usage

Budget data supports `--scope project` and `--scope session --scope-session ID`;
global remains the default. All commands accept `--json`. Session-scope status
includes imported usage; a budget overrun is successful report data, not an exit failure.
See [scope and CLI contract](../docs/cli-contract.md).

```bash
token-budget set daily 5.00
token-budget set session 1.00
token-budget set monthly 50.00
token-budget status
token-budget reset session
token-budget alert --threshold 80
```

## Notes

- Budget data is stored in `~/.ai-skills-data/budget.json`.
- `session` reset clears the accumulated session spend without deleting the configured limit.
- `status` imports available Claude/Gemini usage before checking daily/monthly totals.
  Set `AI_USAGE_AUTO_IMPORT=0` for read-only status. Historical imports do not increment
  the live session counter; records with unknown prices are excluded with a warning.
