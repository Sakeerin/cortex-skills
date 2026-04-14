---
name: prompt-lib
description: Personal prompt library — store, search, and reuse prompt templates with variable substitution
providers: claude, gemini, openai, ollama, generic
---

# prompt-lib

> Store reusable prompt templates and inject them into any AI session instantly.
> Supports `{{variable}}` placeholders for dynamic substitution.

## When to Use

Activate when the user:
- Asks to save a prompt for later reuse
- Says "use my code-review prompt"
- Wants to list or search saved prompts
- Mentions a named prompt template

## Usage

```bash
python3 ~/.ai-skills/prompt-lib/scripts/prompt_lib.py <command>
# or via wrapper:
prompt-lib <command>
```

### Add a prompt

```bash
prompt-lib add "code-review" "Review this {{language}} code for quality, security, and performance:\n\n{{code}}"
prompt-lib add "commit-msg" "Write a conventional commit message for these changes:\n\n{{diff}}" --tag git
prompt-lib add "thai-translate" "แปลข้อความต่อไปนี้เป็นภาษาไทยที่เป็นธรรมชาติ:\n\n{{text}}" --tag thai
```

### List / Search

```bash
prompt-lib list               # all prompts
prompt-lib list --tag git     # filter by tag
prompt-lib search "review"    # keyword search
```

### Use a prompt

```bash
prompt-lib use "code-review"                                    # print as-is
prompt-lib use "code-review" --with language=TypeScript         # fill one variable
prompt-lib use "commit-msg" --with "diff=$(git diff --staged)"  # fill from command
```

### Edit / Delete

```bash
prompt-lib edit "code-review"   # opens $EDITOR
prompt-lib delete "code-review"
```

### Export / Import

```bash
prompt-lib export > my-prompts.json
prompt-lib import my-prompts.json
prompt-lib import shared-prompts.json --overwrite
```

## Template Syntax

Use `{{variable_name}}` for placeholders:

```
Review the following {{language}} code and check for:
- Code quality and readability
- Security vulnerabilities
- Performance issues

Code:
{{code}}
```

Substitute with `--with variable=value` (repeatable). Unfilled variables are preserved and a warning is shown.

## Data

Stored at `$AI_SKILLS_DATA_DIR/prompts.json` (default: `~/.ai-skills-data/prompts.json`).

```json
{
  "code-review": {
    "name": "code-review",
    "content": "Review this {{language}} code...",
    "description": "Code review template",
    "tags": ["review", "code"],
    "created_at": "ISO8601",
    "updated_at": "ISO8601"
  }
}
```

## Notes

- Requires Python 3.11+
- Edit command uses `$EDITOR` env var (defaults to `nano` / `notepad`)
- `use` output goes to stdout — pipe or redirect as needed: `prompt-lib use code-review | pbcopy`
