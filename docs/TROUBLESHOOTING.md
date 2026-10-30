# Troubleshooting Guide

Common issues and how to resolve them.

---

## Quick Diagnosis

Always start here:

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --fix
```

This checks provider config, API keys, local server connectivity, and data directory.

---

## Installation Issues

### `python3: command not found`

**Cause:** Python not installed or not on PATH.

```bash
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo apt install python3.12

# Windows — use py launcher
py -3 --version

# Check PATH
which python3 || which python
```

### `ModuleNotFoundError: No module named 'env_loader'`

**Cause:** Running a script from the wrong directory, or `_lib` path not resolving.

```bash
# Always run scripts with full path from anywhere
python3 ~/.ai-skills/todo/scripts/tasks.py list

# Verify _lib exists
ls ~/.ai-skills/_lib/

# Check the script's path is correct
head -35 ~/.ai-skills/todo/scripts/tasks.py | grep _LIB_DIR
```

### `Permission denied` on shell wrapper

```bash
chmod +x ~/.ai-skills/todo/todo
# Or fix all wrappers at once:
find ~/.ai-skills -maxdepth 2 -name "$(basename *)" -not -name "*.py" -not -name "*.md" -not -name "*.sh" -exec chmod +x {} \;
```

---

## Provider / API Issues

### `API key not found` or `401 Unauthorized`

**Cause:** API key not set or incorrect.

```bash
# Check what's loaded
python3 -c "import sys; sys.path.insert(0,'~/.ai-skills/_lib'); from env_loader import get; print(get('ANTHROPIC_API_KEY', 'NOT SET'))"

# Check the env file
cat ~/.ai-skills.env

# Verify key format (Claude)
# Should start with: sk-ant-api03-...
```

**Fix:**
```bash
# Edit the config file
nano ~/.ai-skills.env

# Add the missing key
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### `connection refused` — Ollama not running

```bash
# Check if Ollama is running
curl http://localhost:11434

# Start Ollama
ollama serve

# On Linux (systemd)
sudo systemctl start ollama
sudo systemctl enable ollama  # auto-start on boot

# Check which models are available
ollama list
```

### `connection refused` — LM Studio not running

1. Open LM Studio
2. Go to "Local Server" tab
3. Click "Start Server" (port 1234)
4. Load a model before testing

### Claude API — `overloaded_error`

Claude is temporarily overloaded. Wait a few seconds and retry.

### Gemini — `RESOURCE_EXHAUSTED`

Free tier quota exceeded. Either wait until quota resets (daily) or use a paid tier.

---

## Data Issues

### Tasks/notes disappeared

**Cause:** JSONL compaction moved data (unlikely), or wrong `AI_SKILLS_DATA_DIR`.

```bash
# Check where data is stored
python3 -c "import sys; sys.path.insert(0,'~/.ai-skills/_lib'); from env_loader import get_data_dir; print(get_data_dir())"

# List data files
ls -la ~/.ai-skills-data/

# View raw JSONL
cat ~/.ai-skills-data/todos.jsonl
```

### Corrupted JSONL file

If you see `Warning: skipping corrupted line in todos.jsonl`:

```bash
# View the file to find corrupt lines
cat -n ~/.ai-skills-data/todos.jsonl

# Remove a specific bad line (e.g., line 42)
sed -i '42d' ~/.ai-skills-data/todos.jsonl

# Or repair by exporting good records and reimporting
python3 ~/.ai-skills/todo/scripts/tasks.py export --format markdown > backup.md
# Manually recreate tasks if needed
```

### Migrate data to a new directory

```bash
# 1. Copy existing data
cp -r ~/.ai-skills-data /new/path/

# 2. Update config
echo "AI_SKILLS_DATA_DIR=/new/path" >> ~/.ai-skills.env

# 3. Verify
python3 ~/.ai-skills/env-check/scripts/env_check.py
```

### JSONL file is very large / slow

Compact it manually:

```python
# Run from Python
import sys
sys.path.insert(0, "~/.ai-skills/_lib")
from env_loader import get_data_dir
from jsonl_store import JSONLStore

store = JSONLStore(get_data_dir() / "todos.jsonl")
removed = store.compact()
print(f"Removed {removed} historical events")
```

---

## PATH Issues

### Skill wrappers not found after PATH setup

```bash
# Check if PATH contains skill directories
echo $PATH | tr ':' '\n' | grep ai-skills

# Re-apply PATH setup (bash/zsh)
for d in "$HOME/.ai-skills"/*/; do export PATH="$d:$PATH"; done

# Verify a specific skill
which todo    # should show ~/.ai-skills/todo/todo
which notes   # should show ~/.ai-skills/notes/notes

# If using fish
fish -c "which todo"
```

### PATH setup not persisting after shell restart

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'for d in "$HOME/.ai-skills"/*/; do export PATH="$d:$PATH"; done' >> ~/.zshrc
source ~/.zshrc
```

---

## Git-summary Issues

### `not a git repository`

```bash
# Run git-summary from inside a git repo
cd /your/project
python3 ~/.ai-skills/git-summary/scripts/git_summary.py

# Or specify a repo explicitly
python3 ~/.ai-skills/git-summary/scripts/git_summary.py --repo /path/to/repo
```

### `git not found`

```bash
# macOS
brew install git

# Ubuntu/Debian
sudo apt install git

# Windows — install Git for Windows from https://git-scm.com
```

---

## Project Brief Issues

### `BRIEF.md not found`

```bash
# Initialize a new brief in the current project
cd /your/project
python3 ~/.ai-skills/project-brief/scripts/project_brief.py init

# Or create manually: BRIEF.md in your project root
```

### `find_brief` traverses too far up

`project-brief` stops at the nearest `.git` directory. If there's no `.git`, it traverses to the filesystem root.

```bash
# Initialize a git repo if you haven't already
git init

# Or create BRIEF.md directly in the intended project root
touch BRIEF.md
```

---

## AI Session Log Issues

### No sessions found

**Claude:** Sessions are read from `~/.claude/projects/**/*.jsonl`.

```bash
# Check if Claude CLI has created any sessions
ls ~/.claude/projects/

# If empty, start a Claude Code session first, then check
```

**Gemini:** Sessions are read from `~/.gemini/`.

```bash
ls ~/.gemini/
```

### Sessions show incomplete token counts

Token counts depend on what the Claude/Gemini CLI logs. Some versions log more detail than others. This is a limitation of the session file format, not a bug in cortex-skills.

---

## Daily Report Issues

### Report shows no data

```bash
# Check that data files exist
ls ~/.ai-skills-data/

# Run individual data sources manually
python3 ~/.ai-skills/todo/scripts/tasks.py list
python3 ~/.ai-skills/notes/scripts/notes.py list

# Try yesterday
python3 ~/.ai-skills/daily-report/scripts/daily_report.py --yesterday
```

### `Invalid date` error

```bash
# Date must be YYYY-MM-DD format
python3 ~/.ai-skills/daily-report/scripts/daily_report.py --date 2026-05-08

# Not:
# --date "May 8" ← invalid
# --date 05/08/2026 ← invalid
```

---

## Windows-Specific Issues

### Emoji shows as `?` or `[]`

```powershell
# Set UTF-8 code page
chcp 65001

# Or use Windows Terminal (better Unicode support)
```

### Shell wrappers don't run in PowerShell/CMD

Shell wrappers (e.g., `todo`, `notes`) are bash scripts and won't run in PowerShell/CMD directly.

**Options:**
1. Use Git Bash or WSL to run wrappers
2. Use Python scripts directly in PowerShell:
   ```powershell
   python $env:USERPROFILE\.ai-skills\todo\scripts\tasks.py list
   ```

### `~` not expanded in env file on Windows

```ini
# This WON'T work on Windows:
AI_SKILLS_DATA_DIR=~/.ai-skills-data

# Use full path instead:
AI_SKILLS_DATA_DIR=C:\Users\YourName\.ai-skills-data
```

---

## env-check Output Explained

```
✅  AI_PROVIDER                    = claude    ← Provider detected
✅  ANTHROPIC_API_KEY              = sk-ant... ← Key present (masked)
✅  Claude API                     reachable   ← HTTP ping to api.anthropic.com succeeded
⚠️  AI_MODEL                       (not set)   ← Optional but recommended
✅  AI_SKILLS_DATA_DIR             = /home/... ← Data dir exists or was created
❌  Ollama server                  offline     ← localhost:11434 not responding
```

- `✅` = OK
- `⚠️` = Warning (missing but optional, or using default)
- `❌` = Error (required but missing or failing)

---

## Still Stuck?

1. Run `python3 ~/.ai-skills/env-check/scripts/env_check.py --all --fix` for full diagnostics
2. Check if the issue is reproduced with a fresh `AI_SKILLS_DATA_DIR`:
   ```bash
   AI_SKILLS_DATA_DIR=/tmp/test-skills python3 ~/.ai-skills/todo/scripts/tasks.py list
   ```
3. Open an issue at [github.com/Sakeerin/cortex-skills/issues](https://github.com/Sakeerin/cortex-skills/issues) with the output of `env-check --all`
