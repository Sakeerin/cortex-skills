#!/usr/bin/env python3
"""
ai_context.py - Show context window information for known models.
"""

from __future__ import annotations

import argparse
import os
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

from ai_provider import detect, get_context_limit, get_context_table, get_model


def _format_int(value: int) -> str:
    return f"{value:,}"


def cmd_show(args) -> None:
    model = args.model or get_model()
    provider = detect()
    limit = get_context_limit(model)
    if limit == 0:
        print(f"Unknown model: {model}", file=sys.stderr)
        raise SystemExit(1)

    used = args.used
    if used is None and os.environ.get("AI_CONTEXT_USED_TOKENS"):
        used = int(os.environ["AI_CONTEXT_USED_TOKENS"])

    buffer_tokens = args.buffer
    if buffer_tokens is None:
        buffer_tokens = int(os.environ.get("AI_CONTEXT_BUFFER", "20000" if limit >= 100000 else "4000"))

    print(f"Context Window - {model}")
    print("-" * 50)
    print(f"Provider:       {provider}")
    print(f"Max Tokens:     {_format_int(limit)}")

    if used is None:
        print("Used:           unknown")
        print("Free:           unknown")
        print(f"Buffer:         {_format_int(buffer_tokens)}")
        print("Hint:           pass --used <tokens> or set AI_CONTEXT_USED_TOKENS")
    else:
        free = max(limit - used, 0)
        used_pct = min((used / limit) * 100, 100) if limit else 0
        free_pct = max(100 - used_pct, 0)
        print(f"Used:           {_format_int(used)} ({used_pct:.1f}%)")
        print(f"Free:           {_format_int(free)} ({free_pct:.1f}%)")
        print(f"Buffer:         {_format_int(buffer_tokens)}")
        if free <= buffer_tokens:
            print("Warning:        low headroom, compact or trim context soon")

    last_message = args.last_message or os.environ.get("AI_LAST_MESSAGE")
    if last_message:
        print(f"Last message:   {last_message}")


def cmd_all(_args) -> None:
    print("Known Context Limits")
    print("-" * 50)
    for model, limit in get_context_table().items():
        print(f"{model:<22} {_format_int(limit):>12}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show model context window information")
    parser.add_argument("--model", help="Model name to inspect")
    parser.add_argument("--used", type=int, help="Used tokens in the current context")
    parser.add_argument("--buffer", type=int, help="Safety buffer before compacting")
    parser.add_argument("--last-message", help="Most recent user or assistant message")
    parser.add_argument("--all", action="store_true", help="Show all known model context limits")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.all:
        cmd_all(args)
    else:
        cmd_show(args)


if __name__ == "__main__":
    main()
