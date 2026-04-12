---
name: todo
description: Task management with priority, tags, and project grouping
providers: claude, gemini, openai, ollama, generic
---

# todo

> Manage tasks with priorities (`low/medium/high/urgent`), tags, and project grouping.
> Data stored as append-only JSONL — no database required.

## When to Use

Activate when the user wants to:
- Add, list, update, or delete tasks
- Check off completed items
- Filter tasks by priority, tag, or project
- Get a Markdown checklist of tasks

## Usage

```bash
# Via Python
python3 ~/.ai-skills/todo/scripts/tasks.py <command> [options]

# Via shell wrapper (if ~/.ai-skills/todo/ is in PATH)
todo <command> [options]
```

### Add a task

```bash
todo add --title "Fix login bug" --priority high --tag backend --project lms
todo add --title "Write docs" --due 2026-04-20
```

### List tasks

```bash
todo list                          # open tasks only
todo list --all                    # all including completed
todo list --priority urgent        # filter by priority
todo list --tag backend            # filter by tag
todo list --project lms            # filter by project
todo list --checked                # completed tasks only
```

### Complete / update / delete

```bash
todo done <id-prefix>              # mark as done
todo update <id> --priority low    # change priority
todo update <id> --tag api --tag v2  # replace tags
todo delete <id-prefix>            # remove task
todo get <id-prefix>               # show full JSON
```

### Export

```bash
todo export --format markdown      # Markdown checklist grouped by project
```

## Priority Levels

| Priority | Icon | Use for |
|---|---|---|
| `urgent` | 🔴 | Must do today, blocking |
| `high` | 🟠 | Important, do this sprint |
| `medium` | 🟡 | Normal priority (default) |
| `low` | 🟢 | Nice to have |

## Data

Stored at `$AI_SKILLS_DATA_DIR/todos.jsonl` (default: `~/.ai-skills-data/todos.jsonl`).

Uses append-only event sourcing — task state is reconstructed by replaying the log.

### Schema

```json
{
  "id": "uuid",
  "title": "...",
  "checked": false,
  "priority": "medium",
  "tags": ["backend", "sprint-3"],
  "project": "lms",
  "due_date": "2026-04-20",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

## Notes

- Requires Python 3.11+
- ID prefix matching: use first 4+ chars of the UUID
- Tags are set as a list; `--tag` is repeatable for `add`, replaces all tags for `update`
