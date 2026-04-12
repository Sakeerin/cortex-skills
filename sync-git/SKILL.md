---
name: sync-git
description: Synchronize the current git repository with remote — pull, auto-commit, push, with conflict handling
providers: claude, gemini, openai, ollama, generic
---

# sync-git

> Synchronize a git repository with remote origin: fetch, pull with rebase, auto-commit, and push.
> Handles stale locks, network errors, stash/pop, and push retry automatically.

## When to Use

Activate when the user says:
- "sync", "sync repo", "sync the repo"
- "push changes", "push everything", "save changes"
- "commit and push"
- Mentions conflicts during synchronization

## Usage

```bash
# Via bash (always works)
bash ~/.ai-skills/sync-git/scripts/sync.sh

# Via shell wrapper (if ~/.ai-skills/sync-git/ is in PATH)
sync-git
```

## Exit Codes

| Code | Meaning | Action |
|---|---|---|
| `0` | ✅ Success | Show stdout summary to user |
| `1` | ⚠️ Worktree detected | See **Fallback: Worktree** below |
| `2` | ❌ Conflict (rebase/stash) | See **Fallback: Conflict** below |
| `3` | ❌ Push failed after 3 retries | See **Fallback: Push Failure** below |
| `4` | ❌ Network/SSH error | Advise user to check SSH agent or connection |

## Fallback: Worktree

When running inside a worktree (exit 1):
1. Commit any uncommitted changes in the worktree branch
2. Switch to the main working tree: `git worktree list`
3. Navigate there and run sync again
4. Optionally merge the worktree branch and clean up with `git worktree remove`

## Fallback: Conflict (exit 2)

When a rebase or stash conflict occurs:
- **Text files**: accept both changes to preserve all data
- **Config/generated files**: prefer remote version for consistency
- Resolve, then: `git add -A && git rebase --continue`
- Run sync again

## Fallback: Push Failure (exit 3)

1. Run `git fetch && git log --oneline HEAD...origin/<branch>` to understand divergence
2. Try: `git pull --rebase origin <branch>`
3. Resolve any conflicts per guidelines above
4. Push again; if it still fails, report to the user

## Notes

- Requires git and bash (works on Linux, macOS, and WSL2 on Windows)
- Only supports a single remote named `origin`
- Auto-commit message format: `sync: auto-commit YYYY-MM-DDTHH:MM:SSZ`
