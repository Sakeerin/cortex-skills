---
name: memory
description: Persistent key-value memory across sessions and AI providers
providers: claude, gemini, openai, ollama, generic
---

# memory

> Store persistent facts, preferences, and context that survive across sessions and work with any AI provider.
> Solves the problem of AI agents forgetting context between sessions.

## When to Use

Activate when the user wants to:
- Remember a preference, fact, or project detail
- Inject saved context into an AI system prompt
- Check what the AI "remembers" about the user/project
- Update or delete a saved memory

## Usage

```bash
python3 ~/.ai-skills/memory/scripts/memory.py <command>
# or via wrapper:
memory <command>
```

### Save / Update

```bash
memory add user_pref "ชอบใช้ TypeScript strict mode"
memory add project "ชื่อโปรเจกต์: LMS, stack: Laravel 11 + Vue 3 + Inertia"
memory add coding_style "ไม่ชอบ callback hell, ชอบ async/await" --tag preference
memory add db_conventions "money stored as integer satang (THB)" --tag project --tag db
```

If `KEY` already exists, the value is updated (not duplicated).

### Read

```bash
memory list                    # all entries
memory list --tag project      # filter by tag
memory get user_pref           # get one value
memory search "TypeScript"     # keyword search
```

### Inject into AI

```bash
memory context                 # print Markdown block for system prompt injection
```

**Output example:**
```markdown
## Persistent Memory

- **coding_style**: ไม่ชอบ callback hell, ชอบ async/await _(tags: preference)_
- **project**: ชื่อโปรเจกต์: LMS, stack: Laravel 11 + Vue 3 + Inertia
- **user_pref**: ชอบใช้ TypeScript strict mode
```

Paste this into your AI's system prompt so it "remembers" across sessions.

### Delete / Clear

```bash
memory delete user_pref        # delete one entry
memory clear                   # delete all entries
```

### Export

```bash
memory export                  # JSONL to stdout
memory export > backup.jsonl   # save to file
```

## Data

Stored at `$AI_SKILLS_DATA_DIR/memory.jsonl` (default: `~/.ai-skills-data/memory.jsonl`).

Uses append-only JSONL — deletes are soft-deleted events, not physical removal.

```json
{
  "id": "uuid",
  "key": "user_pref",
  "value": "ชอบใช้ TypeScript strict mode",
  "tags": ["preference"],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

## Notes

- Requires Python 3.11+
- Keys are case-sensitive
- Partial key prefix matching supported for `get` (e.g. `memory get user` matches `user_pref` if unique)
- `memory context` output is designed to paste directly as AI system prompt context
