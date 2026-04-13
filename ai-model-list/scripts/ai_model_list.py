#!/usr/bin/env python3
"""
ai_model_list.py - List known or live models per provider.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR.parent / "_lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from ai_provider import (
    PROVIDER_METADATA,
    detect,
    get_api_key,
    get_base_url,
    get_context_limit,
    list_supported,
)


def _fetch_remote_models(provider: str) -> list[str] | None:
    base_url = get_base_url(provider)
    if not base_url:
        return None

    meta = PROVIDER_METADATA[provider]
    endpoint = base_url.rstrip("/") + meta["test_path"]
    headers: dict[str, str] = {}
    api_key = get_api_key(provider)
    if provider == "claude" and api_key:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif provider in {"openai", "mistral"} and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider == "gemini" and api_key:
        endpoint += ("&" if "?" in endpoint else "?") + f"key={api_key}"
    elif provider not in {"ollama", "lmstudio"}:
        return None

    try:
        request = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    if provider == "ollama":
        return [item.get("name", "unknown") for item in data.get("models", [])]
    if provider in {"openai", "mistral", "lmstudio"}:
        return [item.get("id", "unknown") for item in data.get("data", [])]
    if provider == "claude":
        return [item.get("id", "unknown") for item in data.get("data", [])]
    if provider == "gemini":
        models = []
        for item in data.get("models", []):
            name = item.get("name", "")
            models.append(name.split("/")[-1] if "/" in name else name)
        return models
    return None


def get_models(provider: str) -> tuple[list[str], str]:
    live_models = _fetch_remote_models(provider)
    if live_models:
        return sorted(set(live_models)), "live"
    return PROVIDER_METADATA[provider]["known_models"], "catalog"


def cmd_list(args) -> None:
    provider = args.provider or detect()
    if provider not in list_supported():
        print(f"Unknown provider: {provider}", file=sys.stderr)
        raise SystemExit(1)
    models, source = get_models(provider)
    print(f"Models - {provider} ({source})")
    print("-" * 50)
    for model in models:
        limit = get_context_limit(model)
        limit_text = f"{limit:,}" if limit else "unknown"
        print(f"{model:<24} context:{limit_text}")


def cmd_compare(_args) -> None:
    print("Provider Model Comparison")
    print("-" * 70)
    for provider in list_supported():
        models, source = get_models(provider)
        for model in models:
            limit = get_context_limit(model)
            limit_text = f"{limit:,}" if limit else "unknown"
            print(f"{provider:<10} {model:<24} context:{limit_text:<10} source:{source}")


def cmd_pull(args) -> None:
    completed = subprocess.run(
        ["ollama", "pull", args.model],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stderr.strip() or "ollama pull failed", file=sys.stderr)
        raise SystemExit(completed.returncode)
    print(completed.stdout.strip() or f"Pulled {args.model}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List models for AI providers")
    parser.add_argument("--provider", choices=list_supported(), help="Provider to inspect")
    parser.add_argument("--compare", action="store_true", help="Compare models across providers")
    parser.add_argument("--pull", metavar="MODEL", help="Pull an Ollama model")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.pull:
        cmd_pull(argparse.Namespace(model=args.pull))
    elif args.compare:
        cmd_compare(args)
    else:
        cmd_list(args)


if __name__ == "__main__":
    main()
