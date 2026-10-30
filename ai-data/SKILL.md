---
name: ai-data
description: Back up and restore AI Skills data, or diagnose and quarantine corrupted records.
---

# AI Data Maintenance

## When to Use

Use when the user wants a data backup, restore, or help with corrupt skill data.
Run from the repository or an installation that includes the shared `_lib` directory.

## Usage

```bash
ai-data backup
ai-data backup --output ./skills-backup.zip
ai-data doctor
ai-data doctor --repair
ai-data restore ./skills-backup.zip --dry-run
ai-data restore ./skills-backup.zip --overwrite
```

Python entrypoint: `python3 ai-data/scripts/ai_data.py`.
Use `--data-dir PATH` before the subcommand to select a different data directory.
Every subcommand supports `--json` for a machine-readable report.
Reports use the shared envelope: read command results from `data`, and check `ok`
and `exit_code`. Scope flags may appear before/after the subcommand:
`ai-data backup --scope project` or `ai-data doctor --scope session --scope-session ID --json`.
`--data-dir` overrides the base root; backup/restore/doctor affect only the selected
namespace, never child scopes. Global remains the default. See [CLI contract](../docs/cli-contract.md).

## Data Safety

- Backups contain known skill data files, not API credentials or source session transcripts.
- Restore validates the archive and checksums before writing. Existing files require `--overwrite`.
- Repair and overwrite restore create a safety backup first. JSONL repair quarantines bad
  lines in `quarantine/`, preserving valid records and event order.
- Malformed JSON documents are reported for manual recovery, rather than replaced with empty data.
- Default archives are saved in `backups/` inside `AI_SKILLS_DATA_DIR`.
- Supported files: `todos.jsonl`, `notes.jsonl`, `memory.jsonl`, `cost-log.jsonl`,
  `prompts.json`, `budget.json`, and `usage-import-state.json`. Archives are limited
  to 256 MiB of uncompressed data. Quarantine files and old backups are not recursively archived.
- Archives are not encrypted. Keep them private because notes and memory can contain sensitive data.
