# cortex-skills — Setup Guide

Complete installation and configuration guide for all supported AI providers.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Provider Configuration](#provider-configuration)
   - [Claude Code](#claude-code)
   - [Gemini CLI](#gemini-cli)
   - [OpenAI / ChatGPT](#openai--chatgpt)
   - [Ollama (Local)](#ollama-local)
   - [Mistral AI](#mistral-ai)
   - [LM Studio (Local)](#lm-studio-local)
4. [PATH Setup](#path-setup)
5. [Verifying Setup](#verifying-setup)
6. [Data Directory](#data-directory)
7. [Updating Skills](#updating-skills)
8. [Uninstalling](#uninstalling)
9. [Platform Notes](#platform-notes)

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| bash | Any | For shell wrappers and `sync-git` |
| git | Any | For `sync-git`, `git-summary` |
| No pip install | — | `_lib` is imported via `sys.path` directly |

---

## Installation

### Option A — Interactive installer (recommended)

```bash
git clone https://github.com/your-username/cortex-skills ~/.ai-skills
bash ~/.ai-skills/install.sh
```

The installer will guide you through:
- Selecting which skills to install
- Configuring your AI provider
- Setting up PATH

### Option B — Clone full repo manually

```bash
git clone https://github.com/your-username/cortex-skills ~/.ai-skills
```

Then configure manually (see [Provider Configuration](#provider-configuration) below).

### Option C — Single skill via degit (no full clone)

```bash
npx degit your-username/cortex-skills/todo ~/.ai-skills/todo
```

---

## Provider Configuration

All configuration lives in `~/.ai-skills.env` (or `.ai-skills.env` in any project folder).

```bash
# Template — copy and fill in your values
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

---

### Claude Code

**Step 1 — Get an API key**

```
https://console.anthropic.com/settings/keys
```

**Step 2 — Configure**

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-api03-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

**Available models**

| Model | Context | Best for |
|---|---|---|
| `claude-opus-4-6` | 200K tokens | Complex tasks, code generation |
| `claude-sonnet-4-6` | 200K tokens | Balanced speed/quality (recommended) |
| `claude-haiku-4-5` | 200K tokens | Fast, simple tasks |

**Step 3 — Verify**

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider claude
```

**Step 4 — Add to Claude Code context (optional)**

Add to your project's `CLAUDE.md`:

```markdown
Skills are at ~/.ai-skills/.
Run: python3 ~/.ai-skills/<skill>/scripts/<script>.py <command>
See ~/.ai-skills/CLAUDE.md for the full skills reference.
```

---

### Gemini CLI

**Step 1 — Get an API key**

```
https://aistudio.google.com/apikey
```

**Step 2 — Configure**

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIzaSy...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

**Available models**

| Model | Context | Best for |
|---|---|---|
| `gemini-2.5-pro` | 1M tokens | Best quality, very large context |
| `gemini-2.5-flash` | 1M tokens | Faster, cheaper |
| `gemini-1.5-pro` | 2M tokens | Maximum context |

**Step 3 — Verify**

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider gemini
```

**Step 4 — Add to GEMINI.md (optional)**

```markdown
Skills are at ~/.ai-skills/.
Run: python3 ~/.ai-skills/<skill>/scripts/<script>.py <command>
```

---

### OpenAI / ChatGPT

**Step 1 — Get an API key**

```
https://platform.openai.com/api-keys
```

**Step 2 — Configure**

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=openai
AI_MODEL=gpt-4o
OPENAI_API_KEY=sk-proj-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

**Available models**

| Model | Context | Notes |
|---|---|---|
| `gpt-4o` | 128K tokens | Latest, multimodal |
| `gpt-4o-mini` | 128K tokens | Fast, cheap |
| `gpt-4.1` | 1M tokens | Latest long-context |

**Step 3 — Verify**

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider openai
```

**Azure OpenAI** — set base URL to your Azure endpoint:

```bash
AI_PROVIDER=openai
AI_MODEL=gpt-4o
OPENAI_API_KEY=<azure-key>
AI_BASE_URL=https://<resource>.openai.azure.com/openai/deployments/<deployment>
```

---

### Ollama (Local)

Run AI models fully offline — no API key required.

**Step 1 — Install Ollama**

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

**Step 2 — Pull a model**

```bash
ollama pull llama3.3         # 70B, best quality
ollama pull llama3.2         # 3B, very fast
ollama pull qwen2.5-coder    # code-focused
ollama pull mistral          # balanced
ollama pull deepseek-r1      # reasoning
```

**Step 3 — Configure**

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=ollama
AI_MODEL=llama3.3
AI_BASE_URL=http://localhost:11434
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

**Step 4 — Start Ollama server**

```bash
ollama serve   # keeps running in background
```

**Step 5 — Verify**

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider ollama
```

> For detailed Ollama setup, see [docs/setup-ollama.md](docs/setup-ollama.md).

---

### Mistral AI

**Step 1 — Get an API key**

```
https://console.mistral.ai/api-keys
```

**Step 2 — Configure**

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=mistral
AI_MODEL=mistral-large-latest
MISTRAL_API_KEY=...
AI_BASE_URL=https://api.mistral.ai/v1
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

**Available models**

| Model | Context | Notes |
|---|---|---|
| `mistral-large-latest` | 128K tokens | Best quality |
| `mistral-small-latest` | 128K tokens | Fast, cheap |
| `codestral-latest` | 256K tokens | Code-focused |

**Step 3 — Verify**

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider mistral
```

---

### LM Studio (Local)

Run any GGUF model locally with an OpenAI-compatible API.

**Step 1 — Install LM Studio**

Download from [lmstudio.ai](https://lmstudio.ai)

**Step 2 — Load a model**

1. Open LM Studio → "My Models" → Download a model
2. Load the model into memory

**Step 3 — Start local server**

In LM Studio → "Local Server" tab → Start Server (default port: 1234)

**Step 4 — Configure**

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=lmstudio
AI_MODEL=lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF
AI_BASE_URL=http://localhost:1234/v1
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

**Step 5 — Verify**

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider lmstudio
```

---

## PATH Setup

Add all skill wrappers to PATH so you can run `todo`, `notes`, `memory`, etc. directly:

### bash / zsh

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'for d in "$HOME/.ai-skills"/*/; do export PATH="$d:$PATH"; done' >> ~/.zshrc
source ~/.zshrc
```

### fish

```fish
# Add to ~/.config/fish/config.fish
for d in ~/\.ai-skills/*/
    fish_add_path $d
end
```

### Windows (PowerShell)

```powershell
# Add to $PROFILE
$skills = Get-ChildItem "$env:USERPROFILE\.ai-skills" -Directory
foreach ($d in $skills) {
    $env:PATH = "$($d.FullName);$env:PATH"
}
```

> **Note:** Skill wrappers are bash scripts — Windows users need Git Bash or WSL.
> Alternatively, use `python3 ~/.ai-skills/<skill>/scripts/<script>.py` directly.

---

## Verifying Setup

```bash
# Check your provider configuration
python3 ~/.ai-skills/env-check/scripts/env_check.py

# Check all providers at once
python3 ~/.ai-skills/env-check/scripts/env_check.py --all

# Get fix suggestions for any failures
python3 ~/.ai-skills/env-check/scripts/env_check.py --fix
```

Expected output (example for Claude):

```
✅  AI_PROVIDER                    = claude
✅  ANTHROPIC_API_KEY              = sk-ant-api0...
✅  Claude API                     reachable
✅  AI_SKILLS_DATA_DIR             = /home/user/.ai-skills-data
```

---

## Data Directory

All skill data lives at `~/.ai-skills-data/` by default.

```
~/.ai-skills-data/
├── todos.jsonl       # Tasks (todo skill)
├── notes.jsonl       # Daily notes
├── memory.jsonl      # Persistent key/value memory
├── prompts.json      # Prompt library
└── cost-log.jsonl    # AI cost tracking
```

**Change the data directory:**

```bash
# In ~/.ai-skills.env
AI_SKILLS_DATA_DIR=/custom/path/to/data
```

**Back up your data:**

```bash
cp -r ~/.ai-skills-data ~/ai-skills-data-backup
```

---

## Per-Project Configuration

To override settings for a specific project, create `.ai-skills.env` in the project root:

```bash
# my-project/.ai-skills.env
AI_PROVIDER=ollama
AI_MODEL=qwen2.5-coder
AI_SKILLS_DATA_DIR=./ai-data   # store data locally in the project
```

Settings cascade: project file → `~/.ai-skills.env` → environment variables.

---

## Updating Skills

```bash
cd ~/.ai-skills
git pull
```

---

## Uninstalling

```bash
# Remove the skills directory
rm -rf ~/.ai-skills

# Remove config (optional)
rm ~/.ai-skills.env

# Remove data (optional — contains your todos, notes, memory)
rm -rf ~/.ai-skills-data

# Remove PATH entries from ~/.bashrc or ~/.zshrc
# Delete the line: for d in "$HOME/.ai-skills"/*/; do ...
```

---

## Platform Notes

| Platform | Notes |
|---|---|
| **macOS** | Full support. Use Homebrew Python 3.11+ |
| **Linux** | Full support |
| **Windows** | Use Git Bash or WSL for shell wrappers. Native Python works for all `.py` scripts. See [docs/setup-windows.md](docs/setup-windows.md) |
| **WSL** | Full support — treat as Linux |

---

## Troubleshooting

**`python3: command not found`**

```bash
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo apt install python3.12

# Windows — add Python to PATH during install, or use py launcher
py -3 ~/.ai-skills/env-check/scripts/env_check.py
```

**`ModuleNotFoundError: No module named 'env_loader'`**

Run scripts from the repo root or use the full path:

```bash
python3 ~/.ai-skills/todo/scripts/tasks.py list
```

**Skills not found on PATH**

```bash
# Check if PATH is set correctly
echo $PATH | tr ':' '\n' | grep ai-skills

# Re-run PATH setup
for d in ~/.ai-skills/*/; do export PATH="$d:$PATH"; done
```

**Permission denied on shell wrapper**

```bash
chmod +x ~/.ai-skills/*/
# Or run individual wrapper:
chmod +x ~/.ai-skills/todo/todo
```
