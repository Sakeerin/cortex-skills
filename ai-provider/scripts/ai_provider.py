#!/usr/bin/env python3
"""
ai_provider.py - Provider detection, configuration, and connectivity checks.
"""

from __future__ import annotations

import argparse
import sys
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
    get_context_limit,
    get_provider_details,
    list_supported,
    set_provider,
    test_provider,
)


def cmd_status(_args) -> None:
    details = get_provider_details()
    print("AI Provider Status")
    print("-" * 50)
    print(f"Provider:    {details['display_name']} ({details['provider']})")
    print(f"Model:       {details['model']}")
    print(f"Context:     {get_context_limit(details['model']) or 'unknown'}")
    print(f"Base URL:    {details['base_url'] or 'n/a'}")
    print(f"Local:       {'yes' if details['local'] else 'no'}")
    print(f"Session dir: {details['session_dir'] or 'n/a'}")


def cmd_list(_args) -> None:
    current = detect()
    print("Supported Providers")
    print("-" * 50)
    for provider in list_supported():
        meta = PROVIDER_METADATA[provider]
        marker = "*" if provider == current else " "
        print(
            f"{marker} {provider:<9}  {meta['display_name']:<14}  "
            f"cli:{meta['cli_tool']:<8}  default:{meta['known_models'][0]}"
        )


def cmd_set(args) -> None:
    path = set_provider(
        args.provider,
        model=args.model,
        base_url=args.base_url,
        global_config=args.global_config,
    )
    scope = "global" if args.global_config else "project"
    print(f"Updated {scope} config: {path}")
    print(f"AI_PROVIDER={args.provider}")
    if args.model:
        print(f"AI_MODEL={args.model}")
    if args.base_url:
        print(f"AI_BASE_URL={args.base_url}")


def cmd_test(args) -> None:
    result = test_provider(args.provider)
    print("AI Provider Test")
    print("-" * 50)
    print(f"Provider: {result['provider']}")
    print(f"Endpoint: {result.get('endpoint', 'n/a')}")
    if result["ok"]:
        print(f"Status:   OK ({result.get('status', 'n/a')})")
        if "models_count" in result:
            print(f"Models:   {result['models_count']}")
    else:
        print("Status:   FAILED")
        print(f"Message:  {result.get('message', 'unknown error')}")
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and configure AI providers")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show active provider and config").set_defaults(func=cmd_status)
    sub.add_parser("list", help="List supported providers").set_defaults(func=cmd_list)

    p_set = sub.add_parser("set", help="Set provider in .ai-skills.env")
    p_set.add_argument("provider", choices=list_supported())
    p_set.add_argument("--model", help="Default model name")
    p_set.add_argument("--base-url", help="Custom API base URL")
    p_set.add_argument("--global", dest="global_config", action="store_true", help="Write to ~/.ai-skills.env")
    p_set.set_defaults(func=cmd_set)

    p_test = sub.add_parser("test", help="Check provider connectivity")
    p_test.add_argument("--provider", choices=list_supported(), help="Provider to test")
    p_test.set_defaults(func=cmd_test)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
