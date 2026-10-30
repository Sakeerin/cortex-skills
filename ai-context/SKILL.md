---
name: ai-context
description: Show context window limits and current usage for AI models
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# ai-context

Inspect context window limits for the active model or for all centrally registered models.

## Usage

```bash
ai-context
ai-context --model gpt-4o
ai-context --model team-model --provider openai --json
ai-context --model claude-sonnet-4-6 --used 45231
ai-context --all
```

## Notes

- Limits/aliases come from the [central model registry](../docs/model-registry.md),
  managed by `cortex models`. Unknown models do not inherit unrelated context limits.

- Current usage can be passed with `--used` or via `AI_CONTEXT_USED_TOKENS`.
- `AI_CONTEXT_BUFFER` can set the compacting threshold used in output.
