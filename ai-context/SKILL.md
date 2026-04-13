---
name: ai-context
description: Show context window limits and current usage for AI models
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# ai-context

Inspect context window limits for the active model or for all built-in models.

## Usage

```bash
ai-context
ai-context --model gpt-4o
ai-context --model claude-sonnet-4-6 --used 45231
ai-context --all
```

## Notes

- Current usage can be passed with `--used` or via `AI_CONTEXT_USED_TOKENS`.
- `AI_CONTEXT_BUFFER` can set the compacting threshold used in output.
