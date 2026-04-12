#!/usr/bin/env python3
"""
env_check.py — Check AI API keys and provider connectivity

Usage:
  env_check.py                     # Check current provider
  env_check.py --all               # Check all providers
  env_check.py --provider ollama   # Check specific provider
  env_check.py --fix               # Show remediation hints
"""

import argparse
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Allow importing _lib without pip install
_SKILL_DIR = Path(__file__).resolve().parent.parent   # scripts/ -> env-check/
_LIB_DIR = _SKILL_DIR.parent / "_lib"                 # env-check/ -> repo-root/ -> _lib/
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from env_loader import load_env, get, get_data_dir
from ai_provider import detect as detect_provider, SUPPORTED

# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

def _ok(label: str, value: str = "") -> None:
    suffix = f" = {value}" if value else ""
    print(f"✅  {label:<30}{suffix}")


def _warn(label: str, msg: str = "") -> None:
    suffix = f"  ({msg})" if msg else ""
    print(f"⚠️   {label:<30}{suffix}")


def _fail(label: str, msg: str = "") -> None:
    suffix = f"  ({msg})" if msg else ""
    print(f"❌  {label:<30}{suffix}")


def _fix(msg: str) -> None:
    print(f"   💡 Fix: {msg}")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_core_vars(show_fix: bool) -> None:
    provider = get("AI_PROVIDER")
    model = get("AI_MODEL")
    data_dir = get("AI_SKILLS_DATA_DIR")

    if provider:
        _ok("AI_PROVIDER", provider)
    else:
        _warn("AI_PROVIDER", "not set — auto-detecting")
        if show_fix:
            _fix("Add AI_PROVIDER=claude to ~/.ai-skills.env")

    if model:
        _ok("AI_MODEL", model)
    else:
        _warn("AI_MODEL", "not set")
        if show_fix:
            _fix("Add AI_MODEL=claude-sonnet-4-6 to ~/.ai-skills.env")

    if data_dir:
        _ok("AI_SKILLS_DATA_DIR", data_dir)
    else:
        default = str(Path.home() / ".ai-skills-data")
        _warn("AI_SKILLS_DATA_DIR", f"not set (using {default})")


def check_provider(provider_name: str, show_fix: bool) -> None:
    """Check a specific provider's API key and connectivity."""
    checks = {
        "claude": _check_claude,
        "openai": _check_openai,
        "gemini": _check_gemini,
        "ollama": _check_ollama,
        "mistral": _check_mistral,
        "lmstudio": _check_lmstudio,
    }
    fn = checks.get(provider_name)
    if fn:
        fn(show_fix)
    else:
        _fail(f"Provider '{provider_name}'", "unknown provider")


def _check_claude(show_fix: bool) -> None:
    key = get("ANTHROPIC_API_KEY")
    if key:
        masked = key[:10] + "..." + key[-4:] if len(key) > 14 else "***"
        _ok("ANTHROPIC_API_KEY", f"set ({masked})")
        # Quick connectivity check
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                _ok("Claude API ping", f"{resp.status} OK")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                _fail("Claude API ping", "401 Unauthorized — invalid API key")
                if show_fix:
                    _fix("Check your ANTHROPIC_API_KEY at console.anthropic.com")
            else:
                _warn("Claude API ping", f"HTTP {e.code}")
        except Exception as e:
            _warn("Claude API ping", f"failed ({type(e).__name__})")
    else:
        _fail("ANTHROPIC_API_KEY", "not set")
        if show_fix:
            _fix("Get your key at console.anthropic.com → API Keys")


def _check_openai(show_fix: bool) -> None:
    key = get("OPENAI_API_KEY")
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        _ok("OPENAI_API_KEY", f"set ({masked})")
    else:
        _fail("OPENAI_API_KEY", "not set")
        if show_fix:
            _fix("Get your key at platform.openai.com → API Keys")


def _check_gemini(show_fix: bool) -> None:
    key = get("GOOGLE_API_KEY") or get("GEMINI_API_KEY")
    label = "GOOGLE_API_KEY / GEMINI_API_KEY"
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        _ok(label, f"set ({masked})")
    else:
        _fail(label, "not set")
        if show_fix:
            _fix("Get your key at aistudio.google.com → Get API Key")


def _check_ollama(show_fix: bool) -> None:
    base_url = get("AI_BASE_URL", "http://localhost:11434")
    try:
        url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=3) as resp:
            import json
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            _ok("Ollama server", f"running at {base_url}")
            if models:
                for m in models[:5]:
                    print(f"     └─ {m}")
                if len(models) > 5:
                    print(f"     └─ ... and {len(models) - 5} more")
            else:
                _warn("Ollama models", "no models pulled yet")
                if show_fix:
                    _fix("Run: ollama pull llama3.3")
    except Exception:
        _fail("Ollama server", f"not reachable at {base_url}")
        if show_fix:
            _fix("Start Ollama with: ollama serve")


def _check_mistral(show_fix: bool) -> None:
    key = get("MISTRAL_API_KEY")
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        _ok("MISTRAL_API_KEY", f"set ({masked})")
    else:
        _fail("MISTRAL_API_KEY", "not set")
        if show_fix:
            _fix("Get your key at console.mistral.ai → API Keys")


def _check_lmstudio(show_fix: bool) -> None:
    base_url = get("AI_BASE_URL", "http://localhost:1234")
    try:
        url = base_url.rstrip("/") + "/v1/models"
        with urllib.request.urlopen(url, timeout=3) as resp:
            _ok("LM Studio server", f"running at {base_url}")
    except Exception:
        _fail("LM Studio server", f"not reachable at {base_url}")
        if show_fix:
            _fix("Start LM Studio and enable the local server")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check AI API keys and provider connectivity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--provider", metavar="NAME",
        help=f"Check specific provider ({', '.join(SUPPORTED)})",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Check all supported providers",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Show remediation hints for failures",
    )
    args = parser.parse_args()

    load_env()

    print("AI Environment Check")
    print("─" * 50)

    # Core vars first
    check_core_vars(args.fix)
    print()

    if args.all:
        for p in SUPPORTED:
            print(f"── {p} ──")
            check_provider(p, args.fix)
            print()
    elif args.provider:
        if args.provider not in SUPPORTED:
            print(f"Unknown provider '{args.provider}'. Supported: {', '.join(SUPPORTED)}", file=sys.stderr)
            sys.exit(1)
        check_provider(args.provider, args.fix)
    else:
        # Default: check current provider
        current = detect_provider()
        print(f"── {current} (current) ──")
        if current == "unknown":
            _warn("No provider detected", "set AI_PROVIDER in ~/.ai-skills.env")
            if args.fix:
                _fix("Run: echo 'AI_PROVIDER=claude' >> ~/.ai-skills.env")
        else:
            check_provider(current, args.fix)


if __name__ == "__main__":
    main()
