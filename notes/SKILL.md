---
name: notes
description: Quick note-taking during coding sessions — ephemeral, freeform, tag-able
providers: claude, gemini, openai, ollama, generic
---

# notes

> Capture quick thoughts during a coding session without leaving the terminal.
> Unlike `todo`, notes are freeform and ephemeral — no priority or due dates.

## When to Use

Activate when the user says:
- "note this down", "remember this", "jot down..."
- "I need to check X later"
- "add a note about..."
- "show me my notes"

## Usage

```bash
python3 ~/.ai-skills/notes/scripts/notes.py <command> [options]
# or via wrapper:
notes <command> [options]
```

### Add

```bash
notes add "ต้องเช็ค race condition ใน reservation number"
notes add "idea: เพิ่ม webhook สำหรับ payment callback" --tag idea
notes add "fix auth bug before release" --tag bug --tag urgent
```

### List

```bash
notes list                    # today's open notes (default)
notes list --all              # all notes
notes list --done             # completed notes
notes list --tag idea         # filter by tag
```

### Search / Complete / Delete

```bash
notes search "webhook"        # search by keyword or tag
notes done <id-prefix>        # mark as done
notes delete <id-prefix>      # remove permanently
```

### Export

```bash
notes export                          # Markdown grouped by date
notes export --format markdown        # same
notes export --format jsonl           # raw JSONL
```

## Difference from `todo`

| | `notes` | `todo` |
|---|---|---|
| Purpose | Quick thoughts, reminders | Tracked tasks |
| Priority | None | low/medium/high/urgent |
| Due date | None | Optional |
| Grouping | By date | By project |
| Lifecycle | Ephemeral | Persistent |

## Data

Stored at `$AI_SKILLS_DATA_DIR/notes.jsonl` (default: `~/.ai-skills-data/notes.jsonl`).

```json
{
  "id": "uuid",
  "content": "...",
  "tags": ["idea"],
  "done": false,
  "date": "2026-04-14",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

## Notes

- Requires Python 3.11+
- `list` without flags shows only **today's** open notes
- Tags are set with `--tag` (repeatable): `--tag idea --tag backend`
