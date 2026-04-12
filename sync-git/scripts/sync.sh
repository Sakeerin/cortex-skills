#!/usr/bin/env bash
# sync.sh — Synchronize local git repo with remote origin
# Ported from thaitype/skills (https://github.com/thaitype/skills)
#
# Exit codes:
#   0 = success
#   1 = worktree conflict (not in main working tree)
#   2 = rebase/merge conflict
#   3 = push failed after 3 retries
#   4 = network/SSH connectivity error
set -euo pipefail

EXIT_OK=0
EXIT_WORKTREE=1
EXIT_CONFLICT=2
EXIT_PUSH_FAILED=3
EXIT_NETWORK=4

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() {
    local code="$1"; shift
    echo "❌ $*" >&2
    exit "$code"
}

is_worktree() {
    # Returns 0 (true) if running inside a git worktree (not the main tree)
    local git_dir
    git_dir=$(git rev-parse --git-dir 2>/dev/null) || return 1
    [[ "$git_dir" == *".git/worktrees/"* ]]
}

remove_stale_lock() {
    local lock_file=".git/index.lock"
    if [[ -f "$lock_file" ]]; then
        local lock_age
        # Cross-platform: macOS uses -f %m, Linux uses -c %Y
        if stat -f "%m" "$lock_file" &>/dev/null; then
            lock_age=$(( $(date +%s) - $(stat -f "%m" "$lock_file") ))
        else
            lock_age=$(( $(date +%s) - $(stat -c "%Y" "$lock_file") ))
        fi
        if [[ "$lock_age" -gt 5 ]]; then
            local lock_pid
            lock_pid=$(cat "$lock_file" 2>/dev/null | head -1 || echo "")
            if [[ -z "$lock_pid" ]] || ! kill -0 "$lock_pid" 2>/dev/null; then
                echo "⚠️  Removing stale lock file (age: ${lock_age}s)"
                rm -f "$lock_file"
            fi
        fi
    fi
}

check_network() {
    if ! git ls-remote --exit-code origin HEAD &>/dev/null; then
        die $EXIT_NETWORK "Cannot reach remote 'origin'. Check your network or SSH configuration."
    fi
}

has_conflicts() {
    git diff --diff-filter=U --name-only | grep -q .
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    echo "🔄 Starting git sync..."

    # 1. Worktree check
    if is_worktree; then
        die $EXIT_WORKTREE "Running inside a git worktree. Please run from the main working tree."
    fi

    # 2. Remove stale lock files
    remove_stale_lock

    # 3. Network check
    echo "🌐 Checking remote connectivity..."
    check_network

    # 4. Fetch
    echo "📥 Fetching from origin..."
    git fetch origin

    # 5. Pull with rebase if behind
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD)
    local local_ref remote_ref
    local_ref=$(git rev-parse HEAD)
    remote_ref=$(git rev-parse "origin/$branch" 2>/dev/null || echo "")

    if [[ -n "$remote_ref" && "$local_ref" != "$remote_ref" ]]; then
        local ahead behind
        read -r ahead behind <<< "$(git rev-list --left-right --count HEAD...origin/$branch)"
        if [[ "$behind" -gt 0 ]]; then
            echo "📩 $behind commit(s) behind remote — pulling with rebase..."

            # Stash uncommitted changes if any
            local stashed=false
            if ! git diff --quiet || ! git diff --cached --quiet; then
                echo "📦 Stashing uncommitted changes..."
                git stash push -m "sync-git auto-stash $(date -u +%Y%m%dT%H%M%SZ)"
                stashed=true
            fi

            if ! git pull --rebase origin "$branch"; then
                if has_conflicts; then
                    die $EXIT_CONFLICT "Rebase conflict detected. Resolve conflicts then run sync again."
                fi
                die $EXIT_CONFLICT "Pull/rebase failed."
            fi

            if [[ "$stashed" == "true" ]]; then
                echo "📤 Restoring stashed changes..."
                if ! git stash pop; then
                    if has_conflicts; then
                        die $EXIT_CONFLICT "Stash pop conflict. Resolve manually then run sync again."
                    fi
                fi
            fi
        fi
    fi

    # 6. Stage and commit if there are changes
    if ! git diff --quiet || ! git diff --cached --quiet || \
       [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
        echo "📝 Staging changes..."
        git add -A

        local commit_msg
        commit_msg="sync: auto-commit $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        git commit -m "$commit_msg" || true   # ok if nothing to commit
    fi

    # 7. Push with retry (up to 3 attempts)
    local push_attempt=0
    while [[ $push_attempt -lt 3 ]]; do
        push_attempt=$(( push_attempt + 1 ))
        echo "🚀 Pushing to origin/$branch (attempt $push_attempt/3)..."
        if git push origin "$branch"; then
            break
        fi
        if [[ $push_attempt -ge 3 ]]; then
            die $EXIT_PUSH_FAILED "Push failed after 3 attempts."
        fi
        echo "⚠️  Push rejected, rebasing and retrying..."
        if ! git pull --rebase origin "$branch"; then
            if has_conflicts; then
                die $EXIT_CONFLICT "Conflict during retry rebase. Resolve manually."
            fi
            die $EXIT_CONFLICT "Rebase failed during retry."
        fi
    done

    # 8. Summary
    echo ""
    echo "✅ Sync complete — branch: $branch"
    git log --oneline -3
}

main "$@"
