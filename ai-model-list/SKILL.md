---
name: ai-model-list
description: List available models for each AI provider
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# ai-model-list

List models for the active provider, compare built-in catalogs across providers, or pull an Ollama model locally.

## Usage

```bash
ai-model-list
ai-model-list --provider openai
ai-model-list --provider ollama
ai-model-list --compare
ai-model-list --pull llama3.3
```

## Notes

- For remote providers, the command tries a live API listing first and falls back to the built-in catalog.
- `--pull` shells out to `ollama pull`, so it is only relevant for local Ollama usage.
