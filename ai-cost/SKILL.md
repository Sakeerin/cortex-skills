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
ai-cost import --dry-run
ai-cost import --provider claude
ai-cost import --provider gemini --source ./session.json --json
ai-cost today --no-import
```

## Notes

- Usage is stored in `~/.ai-skills-data/cost-log.jsonl` unless `AI_SKILLS_DATA_DIR` overrides it.
- A manual `log` subcommand is also available for backfilling or testing usage entries.
- Reports and exports automatically import local Claude/Gemini usage first. Disable with
  `--no-import` or `AI_USAGE_AUTO_IMPORT=0`. No network requests or API keys are needed.
- Defaults: Claude `~/.claude/projects`, Gemini `~/.gemini/tmp` session files. Override with
  `AI_CLAUDE_SESSION_DIR` / `AI_GEMINI_SESSION_DIR`, or explicit `import --provider NAME --source PATH`.
- Import recognizes Claude nested `message.usage`, Gemini JSON conversations, JSONL recordings,
  and legacy `usageMetadata`. Only recorded usage is available; it is not an invoice or a live API meter.
- Request IDs prevent double counting copied/repeated records. Increasing streaming counts update
  the existing request. In global/project scope historical imports do not add to the
  legacy live session budget. Session-scope budgets include imported session usage.
- Unchanged session files are skipped. Source transcripts are read-only; their contents are never
  copied into the cost log or backups. Only token counts and source metadata are retained.
- Unknown model prices, missing cache rates, and tool-use pricing produce `cost_usd: null`
  and `pricing_status: unknown`. Reports warn and exclude these records from USD totals,
  while retaining tokens. Optional per-million `cache_read` / `cache_write` rates can be added
  through `cortex models set` or the legacy `cost-rates.json` overlay. Prices are estimates
  from the [shared model registry](../docs/model-registry.md), not live provider invoices.
- Unknown manual-log prices also remain `null`, not silently free. Model names alone never
  imply free local usage when a remote provider is selected.
- Before changing an existing cost log, import creates an `ai-data` compatible safety backup.
  `--dry-run` previews import without writing. Import warnings return exit code 5 for explicit imports.
- All commands accept `--json` using the shared envelope (`data` contains the report).
  Use `--scope project` or `--scope session --scope-session ID` for isolated data and
  conservative source filtering. See [CLI contract](../docs/cli-contract.md).
- See [session usage formats](../docs/usage-import.md) for supported records and limitations.
