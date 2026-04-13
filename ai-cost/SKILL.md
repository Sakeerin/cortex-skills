---
name: ai-cost
description: Track and report cross-provider token cost
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# ai-cost

Report spending by time period, inspect provider/model breakdowns, export usage, and store a simple daily budget.

## Usage

```bash
ai-cost today
ai-cost week
ai-cost month
ai-cost breakdown
ai-cost export --format csv
ai-cost budget set 10
```

## Notes

- Usage is stored in `~/.ai-skills-data/cost-log.jsonl` unless `AI_SKILLS_DATA_DIR` overrides it.
- A manual `log` subcommand is also available for backfilling or testing usage entries.
