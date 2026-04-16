#!/usr/bin/env bash
# install.sh — Interactive installer for cortex-skills
# Usage: bash install.sh [--all] [--skills skill1,skill2] [--dir DIR] [--no-path]
set -euo pipefail

REPO_URL="https://github.com/your-username/cortex-skills"
DEFAULT_INSTALL_DIR="$HOME/.ai-skills"
ENV_FILE="$HOME/.ai-skills.env"

# Colors
RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"; CYAN="\033[36m"; BOLD="\033[1m"; RESET="\033[0m"

info()    { echo -e "${CYAN}ℹ${RESET}  $*"; }
success() { echo -e "${GREEN}✅${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠️ ${RESET} $*"; }
error()   { echo -e "${RED}❌${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; echo "$(printf '─%.0s' $(seq 1 ${#1}))"; }

# All available skills
ALL_SKILLS=(time todo sync-git env-check skill-creator ai-provider ai-context ai-model-list ai-cost token-budget notes prompt-lib memory git-summary project-brief daily-report ai-session-log)

INSTALL_DIR="$DEFAULT_INSTALL_DIR"
INSTALL_ALL=false
SELECTED_SKILLS=()
ADD_TO_PATH=true

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)          INSTALL_ALL=true ;;
        --skills)       IFS=',' read -ra SELECTED_SKILLS <<< "$2"; shift ;;
        --dir)          INSTALL_DIR="$2"; shift ;;
        --no-path)      ADD_TO_PATH=false ;;
        -h|--help)
            echo "Usage: bash install.sh [--all] [--skills skill1,skill2] [--dir DIR] [--no-path]"
            exit 0 ;;
        *) warn "Unknown option: $1" ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------
check_deps() {
    local missing=()
    command -v python3 &>/dev/null || command -v python &>/dev/null || missing+=("python3")
    command -v git &>/dev/null || missing+=("git")
    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required tools: ${missing[*]}"
        error "Please install them and try again."
        exit 1
    fi
    # Prefer python3, fallback to python
    PYTHON=$(command -v python3 2>/dev/null || command -v python)
}

# ---------------------------------------------------------------------------
# Interactive skill selection
# ---------------------------------------------------------------------------
select_skills_interactive() {
    header "cortex-skills Installer"
    echo "Universal AI skill collection for Claude Code, Gemini CLI, Ollama, and more."
    echo ""

    echo "Available skills:"
    local i=1
    for skill in "${ALL_SKILLS[@]}"; do
        printf "  %2d) %s\n" "$i" "$skill"
        ((i++))
    done

    echo ""
    echo "Enter skill numbers separated by spaces (e.g. 1 2 3),"
    echo "or 'all' to install everything, or 'q' to quit:"
    read -r selection

    if [[ "$selection" == "q" ]]; then
        echo "Aborted."
        exit 0
    elif [[ "$selection" == "all" ]]; then
        SELECTED_SKILLS=("${ALL_SKILLS[@]}")
    else
        for num in $selection; do
            if [[ "$num" =~ ^[0-9]+$ ]] && (( num >= 1 && num <= ${#ALL_SKILLS[@]} )); then
                SELECTED_SKILLS+=("${ALL_SKILLS[$((num-1))]}")
            else
                warn "Invalid selection: $num (skipping)"
            fi
        done
    fi
}

# ---------------------------------------------------------------------------
# Install a single skill
# ---------------------------------------------------------------------------
install_skill() {
    local skill="$1"
    local dest="$INSTALL_DIR/$skill"

    # Check if git is available and clone from repo
    if command -v git &>/dev/null; then
        if [[ -d "$dest" ]]; then
            info "Updating $skill..."
            git -C "$dest" pull --quiet 2>/dev/null || true
        else
            info "Installing $skill..."
            git clone --quiet --depth=1 --filter=blob:none --sparse "$REPO_URL" "$dest.tmp" 2>/dev/null && \
            git -C "$dest.tmp" sparse-checkout set "$skill" && \
            mv "$dest.tmp/$skill" "$dest" && \
            rm -rf "$dest.tmp" || {
                # Fallback: try degit
                if command -v npx &>/dev/null; then
                    npx --yes degit "$REPO_URL/$skill" "$dest" --quiet 2>/dev/null
                else
                    warn "Cannot install $skill: git sparse-checkout failed and npx not available"
                    return 1
                fi
            }
        fi
    elif command -v npx &>/dev/null; then
        info "Installing $skill via degit..."
        npx --yes degit "$REPO_URL/$skill" "$dest" --quiet 2>/dev/null
    else
        error "Neither git nor npx found. Cannot install skills."
        exit 1
    fi

    # Make wrapper executable
    local wrapper="$dest/$skill"
    [[ -f "$wrapper" ]] && chmod +x "$wrapper"
    # Make Python scripts executable
    find "$dest/scripts" -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
    find "$dest/scripts" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

    success "Installed $skill → $dest"
}

# ---------------------------------------------------------------------------
# Configure provider
# ---------------------------------------------------------------------------
configure_provider() {
    header "Provider Configuration"

    if [[ -f "$ENV_FILE" ]]; then
        info "Found existing config at $ENV_FILE"
        echo "  Current contents:"
        grep -v "API_KEY\|SECRET" "$ENV_FILE" 2>/dev/null | sed 's/^/  /' || true
        echo ""
        read -rp "Reconfigure? [y/N] " answer
        [[ "${answer,,}" != "y" ]] && return
    fi

    echo ""
    echo "Which AI provider will you use primarily?"
    echo "  1) Claude (Anthropic)"
    echo "  2) Gemini (Google)"
    echo "  3) OpenAI / ChatGPT"
    echo "  4) Ollama (local)"
    echo "  5) Mistral"
    echo "  6) Skip (configure manually later)"
    read -rp "Choice [1-6]: " choice

    case "$choice" in
        1)
            PROVIDER="claude"
            MODEL_DEFAULT="claude-sonnet-4-6"
            KEY_VAR="ANTHROPIC_API_KEY"
            KEY_HINT="Get your key at console.anthropic.com"
            ;;
        2)
            PROVIDER="gemini"
            MODEL_DEFAULT="gemini-2.5-flash"
            KEY_VAR="GOOGLE_API_KEY"
            KEY_HINT="Get your key at aistudio.google.com"
            ;;
        3)
            PROVIDER="openai"
            MODEL_DEFAULT="gpt-4o"
            KEY_VAR="OPENAI_API_KEY"
            KEY_HINT="Get your key at platform.openai.com"
            ;;
        4)
            PROVIDER="ollama"
            MODEL_DEFAULT="llama3.3"
            KEY_VAR=""
            KEY_HINT="Make sure Ollama is running: ollama serve"
            ;;
        5)
            PROVIDER="mistral"
            MODEL_DEFAULT="mistral-large"
            KEY_VAR="MISTRAL_API_KEY"
            KEY_HINT="Get your key at console.mistral.ai"
            ;;
        *)
            info "Skipping provider configuration."
            info "Edit $ENV_FILE manually when ready."
            return
            ;;
    esac

    read -rp "Model name [$MODEL_DEFAULT]: " model_input
    MODEL="${model_input:-$MODEL_DEFAULT}"

    API_KEY=""
    if [[ -n "$KEY_VAR" ]]; then
        echo "  $KEY_HINT"
        read -rsp "  Enter $KEY_VAR (hidden, leave blank to skip): " API_KEY
        echo ""
    fi

    # Write config
    {
        echo "# cortex-skills config — $(date +%Y-%m-%d)"
        echo "AI_PROVIDER=$PROVIDER"
        echo "AI_MODEL=$MODEL"
        [[ -n "$API_KEY" ]] && echo "$KEY_VAR=$API_KEY"
        echo "AI_SKILLS_DATA_DIR=$HOME/.ai-skills-data"
    } > "$ENV_FILE"

    chmod 600 "$ENV_FILE"
    success "Config written to $ENV_FILE"
}

# ---------------------------------------------------------------------------
# PATH setup
# ---------------------------------------------------------------------------
setup_path() {
    [[ "$ADD_TO_PATH" == "false" ]] && return

    local shell_rc=""
    if [[ -f "$HOME/.zshrc" ]]; then
        shell_rc="$HOME/.zshrc"
    elif [[ -f "$HOME/.bashrc" ]]; then
        shell_rc="$HOME/.bashrc"
    elif [[ -f "$HOME/.bash_profile" ]]; then
        shell_rc="$HOME/.bash_profile"
    fi

    local path_snippet='# cortex-skills PATH
for _d in "$HOME/.ai-skills"/*/; do
  [[ -d "$_d" ]] && export PATH="$_d:$PATH"
done'

    if [[ -n "$shell_rc" ]]; then
        if grep -q "cortex-skills PATH" "$shell_rc" 2>/dev/null; then
            info "PATH already configured in $shell_rc"
        else
            echo "" >> "$shell_rc"
            echo "$path_snippet" >> "$shell_rc"
            success "Added skill wrappers to PATH in $shell_rc"
            info "Run: source $shell_rc  (or open a new terminal)"
        fi
    else
        warn "Could not find shell rc file. Add this to your shell config manually:"
        echo ""
        echo "$path_snippet"
        echo ""
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    check_deps

    # Determine skills to install
    if [[ "$INSTALL_ALL" == "true" ]]; then
        SELECTED_SKILLS=("${ALL_SKILLS[@]}")
    elif [[ ${#SELECTED_SKILLS[@]} -eq 0 ]]; then
        select_skills_interactive
    fi

    if [[ ${#SELECTED_SKILLS[@]} -eq 0 ]]; then
        error "No skills selected. Exiting."
        exit 1
    fi

    # Create install dir
    mkdir -p "$INSTALL_DIR"
    info "Installing to $INSTALL_DIR/"
    echo ""

    # Install each skill
    local failed=()
    for skill in "${SELECTED_SKILLS[@]}"; do
        install_skill "$skill" || failed+=("$skill")
    done

    echo ""
    header "Summary"
    local installed=$(( ${#SELECTED_SKILLS[@]} - ${#failed[@]} ))
    success "Installed: $installed / ${#SELECTED_SKILLS[@]} skills"
    [[ ${#failed[@]} -gt 0 ]] && warn "Failed: ${failed[*]}"

    # Configure provider (only if not silent/scripted)
    if [[ -t 0 ]]; then
        configure_provider
        setup_path
    fi

    echo ""
    header "Next Steps"
    echo "  1. Run: env-check --fix       (verify your API keys)"
    echo "  2. Run: todo list             (test the todo skill)"
    echo "  3. Run: memory context        (generate AI system prompt context)"
    echo ""
    info "Full docs: $INSTALL_DIR/README.md"
}

main "$@"
