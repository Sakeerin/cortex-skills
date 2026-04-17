#!/usr/bin/env bash
# demo.sh — Interactive demo of cortex-skills
# Usage: bash demo.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Colors
CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"; BOLD="\033[1m"; RESET="\033[0m"

header() { echo -e "\n${BOLD}${CYAN}═══ $* ═══${RESET}"; }
step()   { echo -e "\n${GREEN}▶${RESET} $*"; }
cmd()    { echo -e "  ${YELLOW}\$${RESET} $*"; eval "$*" 2>&1 | sed 's/^/  /'; }
pause()  { echo ""; read -rp "  Press Enter to continue..."; }

export AI_SKILLS_DATA_DIR="$(mktemp -d)"
trap 'rm -rf "$AI_SKILLS_DATA_DIR"' EXIT
echo -e "${CYAN}Demo data dir: $AI_SKILLS_DATA_DIR (cleaned up on exit)${RESET}"

# ---------------------------------------------------------------------------
header "1. env-check — Verify your setup"
# ---------------------------------------------------------------------------
step "Check environment configuration"
cmd "$PYTHON $REPO_DIR/env-check/scripts/env_check.py"
pause

# ---------------------------------------------------------------------------
header "2. todo — Task management"
# ---------------------------------------------------------------------------
step "Add some tasks"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py add --title 'Review PR #42' --priority high --tag dev --project cortex"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py add --title 'Write demo script' --priority medium --tag docs"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py add --title 'Fix login bug' --priority urgent --tag dev"

step "List all tasks"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py list"

step "Mark a task done"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py list --format id 2>/dev/null | head -1 | xargs -I{} $PYTHON $REPO_DIR/todo/scripts/tasks.py done {} 2>/dev/null || true"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py list --priority urgent"

step "Export as markdown"
cmd "$PYTHON $REPO_DIR/todo/scripts/tasks.py export --format markdown"
pause

# ---------------------------------------------------------------------------
header "3. notes — Daily notes"
# ---------------------------------------------------------------------------
step "Capture notes"
cmd "$PYTHON $REPO_DIR/notes/scripts/notes.py add 'Standup: shipping auth refactor today'"
cmd "$PYTHON $REPO_DIR/notes/scripts/notes.py add 'Remember: check Redis cache expiry'"
cmd "$PYTHON $REPO_DIR/notes/scripts/notes.py list"
pause

# ---------------------------------------------------------------------------
header "4. memory — Persistent key/value store"
# ---------------------------------------------------------------------------
step "Store context for AI agents"
cmd "$PYTHON $REPO_DIR/memory/scripts/memory.py add 'stack' 'Python 3.12, FastAPI, PostgreSQL, Redis'"
cmd "$PYTHON $REPO_DIR/memory/scripts/memory.py add 'conventions' 'snake_case vars, type hints required, async preferred'"
cmd "$PYTHON $REPO_DIR/memory/scripts/memory.py add 'team' 'Alice (backend), Bob (frontend), Carol (devops)'"

step "List memory"
cmd "$PYTHON $REPO_DIR/memory/scripts/memory.py list"

step "Generate AI context block"
cmd "$PYTHON $REPO_DIR/memory/scripts/memory.py context"
pause

# ---------------------------------------------------------------------------
header "5. prompt-lib — Prompt library"
# ---------------------------------------------------------------------------
step "Add a template prompt"
cmd "$PYTHON $REPO_DIR/prompt-lib/scripts/prompt_lib.py add code-review 'Review this {{language}} code for bugs, style, and performance:\n\n{{code}}' --description 'Standard code review'"
cmd "$PYTHON $REPO_DIR/prompt-lib/scripts/prompt_lib.py add commit-msg 'Write a conventional commit message for: {{changes}}' --tag git"

step "List prompts"
cmd "$PYTHON $REPO_DIR/prompt-lib/scripts/prompt_lib.py list"

step "Use a prompt with variable substitution"
cmd "$PYTHON $REPO_DIR/prompt-lib/scripts/prompt_lib.py use code-review --with language=Python --with code='def add(a,b): return a+b'"
pause

# ---------------------------------------------------------------------------
header "6. git-summary — Git diff summaries"
# ---------------------------------------------------------------------------
step "Summarise recent commits"
cmd "$PYTHON $REPO_DIR/git-summary/scripts/git_summary.py --last 3 --repo $REPO_DIR"
pause

# ---------------------------------------------------------------------------
header "7. daily-report — Standup generator"
# ---------------------------------------------------------------------------
step "Generate today's daily report"
cmd "$PYTHON $REPO_DIR/daily-report/scripts/daily_report.py"

step "Slack format"
cmd "$PYTHON $REPO_DIR/daily-report/scripts/daily_report.py --format slack"
pause

# ---------------------------------------------------------------------------
header "8. skill-creator — Scaffold a new skill"
# ---------------------------------------------------------------------------
step "List all installed skills"
cmd "$PYTHON $REPO_DIR/skill-creator/scripts/skill_creator.py list"

step "Validate a skill"
cmd "$PYTHON $REPO_DIR/skill-creator/scripts/skill_creator.py validate todo"
pause

# ---------------------------------------------------------------------------
echo -e "\n${GREEN}${BOLD}Demo complete!${RESET}"
echo ""
echo "Next steps:"
echo "  1. Run: bash install.sh            (full interactive install)"
echo "  2. Read: CONTRIBUTING.md           (add your own skills)"
echo "  3. Run: pytest tests/ -v           (run integration tests)"
echo ""
