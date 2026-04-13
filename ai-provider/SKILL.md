---
name: ai-provider
description: Detect, configure, and test the active AI provider
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# ai-provider

Inspect which provider is active, persist a default provider/model, and run a quick connectivity test.

## Usage

```bash
ai-provider status
ai-provider list
ai-provider set claude --model claude-sonnet-4-6
ai-provider set ollama --base-url http://localhost:11434
ai-provider test
ai-provider test --provider openai
```

## Notes

- `set` writes to `.ai-skills.env` in the current project by default.
- Use `--global` to write to `~/.ai-skills.env` instead.
- Remote provider tests require the matching API key to be present.
