---
name: env-check
description: Check AI API keys and provider connectivity before starting work
providers: claude, gemini, openai, ollama, mistral, lmstudio
---

# env-check

> Verify AI environment: env vars, API keys, and connectivity status.
> Use this at the start of a session to confirm everything is configured correctly.

## When to Use

Activate when the user:
- Asks "is my Claude / OpenAI / Gemini setup working?"
- Gets authentication errors or connectivity failures
- Wants to confirm which provider is active
- Says "check my AI config" or "check env"

## Usage

```bash
# Via Python
python3 ~/.ai-skills/env-check/scripts/env_check.py

# Via shell wrapper
env-check
```

### Options

```bash
env-check                       # Check current provider (auto-detected)
env-check --provider ollama     # Check specific provider
env-check --all                 # Check all providers
env-check --fix                 # Show remediation hints for failures
env-check --provider claude --fix  # Check Claude with fix hints
```

### Example Output

```
AI Environment Check
──────────────────────────────────────────────────
✅  AI_PROVIDER                 = claude
✅  AI_MODEL                    = claude-sonnet-4-6
⚠️   AI_SKILLS_DATA_DIR          not set (using ~/.ai-skills-data)

── claude (current) ──
✅  ANTHROPIC_API_KEY           set (sk-ant-api0...xxxx)
✅  Claude API ping             200 OK
```

### With `--fix`

```
❌  ANTHROPIC_API_KEY           not set
   💡 Fix: Get your key at console.anthropic.com → API Keys
```

## Providers Supported

| Provider | Key Checked | Connectivity |
|---|---|---|
| `claude` | `ANTHROPIC_API_KEY` | API ping to `api.anthropic.com` |
| `openai` | `OPENAI_API_KEY` | Key presence only |
| `gemini` | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Key presence only |
| `ollama` | None (local) | HTTP ping to `localhost:11434` |
| `mistral` | `MISTRAL_API_KEY` | Key presence only |
| `lmstudio` | None (local) | HTTP ping to `localhost:1234` |

## Config File

Create `~/.ai-skills.env` to set defaults:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
```

## Notes

- Requires Python 3.11+
- API keys are masked in output (only first/last chars shown)
- `NO_COLOR=1` disables color output
