---
name: time
description: Get the current local date and time
providers: claude, gemini, openai, ollama, generic
---

# time

> Get the current local date and time from the system.

## When to Use

Activate when the user asks about:
- Current time or date
- Today's date / "what day is it"
- Current datetime or timezone

## Usage

```bash
date
```

That's it. The system `date` command returns the current local time with timezone.

### Example Output

```
Sun Apr 12 14:35:22 +07 2026
```

### With formatting

```bash
date "+%Y-%m-%d %H:%M:%S %Z"   # 2026-04-12 14:35:22 +07
date -u                          # UTC time
```

## Notes

- No Python required — uses the system `date` command
- Works on all Unix/Linux/macOS systems
- On Windows, use `Get-Date` in PowerShell or run via WSL2
