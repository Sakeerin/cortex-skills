---
name: git-summary
description: Human-readable summary of git diff/log — no AI API needed
providers: claude, gemini, openai, ollama, generic
---

# git-summary

> Quickly understand what changed in a repo without reading raw git output.
> Use `--format prompt` to generate a ready-to-paste block for AI commit message generation.

## When to Use

Activate when the user:
- Asks "what changed?", "what did I do today?", "show me the diff"
- Wants a commit message suggestion
- Says "summarize the recent commits"
- Wants to see staged vs unstaged changes

## Usage

```bash
python3 ~/.ai-skills/git-summary/scripts/git_summary.py [options]
# or via wrapper:
git-summary [options]
```

### Default (unstaged changes)

```bash
git-summary
```

```
Unstaged changes  (42 insertions, 7 deletions)
  - app/Services/PaymentService.php (+38, -2)
  - app/Http/Controllers/PaymentController.php (+4, -5)
```

### Staged changes

```bash
git-summary --staged
```

### Recent commits

```bash
git-summary --last 5          # last 5 commits
git-summary --since yesterday # commits since yesterday
git-summary --since 2026-04-01
```

### Diff vs another branch

```bash
git-summary --branch main
```

### For AI commit message generation

```bash
git-summary --staged --format prompt
```

**Output:**
```
Please write a conventional commit message for these changes:

Files changed (3):
- app/Services/PaymentService.php (+120, -5)
- app/Http/Controllers/PaymentController.php (+45, -12)
- tests/Feature/PaymentTest.php (+89, -0)

Summary: 254 insertions(+), 17 deletions(-)
```

Paste this into any AI chat to get a commit message.

## Notes

- Requires Python 3.11+ and git
- No AI API calls — purely reads git output
- Works in any directory inside a git repository
- `--since` accepts git date formats: `yesterday`, `1 week ago`, `2026-04-01`
