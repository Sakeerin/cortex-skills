---
name: token-budget
description: Manage daily, session, and monthly AI cost budgets
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# token-budget

Set and inspect daily, session, and monthly budgets that are backed by the shared cost tracker.

## Usage

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
