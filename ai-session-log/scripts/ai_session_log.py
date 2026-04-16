#!/usr/bin/env python3
"""
ai_session_log.py — Unified session log across AI providers

Usage:
  ai_session_log.py --latest              # most recent session
  ai_session_log.py --latest --count 5   # last 5 sessions
  ai_session_log.py --provider claude    # Claude sessions only
  ai_session_log.py --search "keyword"   # search session content
  ai_session_log.py --export markdown    # export latest as Markdown
  ai_session_log.py --stats              # session statistics
"""

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR.parent / "_lib"
_ADAPTERS_DIR = _SKILL_DIR / "adapters"

for d in [str(_LIB_DIR), str(_ADAPTERS_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

from env_loader import get
from ai_provider import detect as detect_provider


def _get_adapter(provider: str):
    """Return the adapter module for the given provider, or None."""
    if provider == "claude":
        try:
            import claude_adapter
            return claude_adapter
        except ImportError:
            return None
    elif provider == "gemini":
        try:
            import gemini_adapter
            return gemini_adapter
        except ImportError:
            return None
    return None


def _all_sessions(provider: str | None, limit: int = 50) -> list[dict]:
    providers = [provider] if provider else ["claude", "gemini"]
    sessions = []
    for p in providers:
        adapter = _get_adapter(p)
        if adapter:
            sessions.extend(adapter.list_sessions(limit=limit))
    sessions.sort(key=lambda s: s.get("end_time") or s.get("start_time") or "", reverse=True)
    return sessions[:limit]


def _fmt_number(n: int) -> str:
    return f"{n:,}" if n else "0"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_latest(args):
    count = args.count
    sessions = _all_sessions(args.provider, limit=max(count, 20))[:count]

    if not sessions:
        prov = args.provider or "any provider"
        print(f"No sessions found for {prov}.")
        print("Sessions are read from ~/.claude/projects/ (Claude) and ~/.gemini/ (Gemini).")
        return

    for s in sessions:
        turns = s.get("turns", "?")
        duration = s.get("duration", "")
        tokens_in = _fmt_number(s.get("input_tokens", 0))
        tokens_out = _fmt_number(s.get("output_tokens", 0))
        dt = (s.get("start_time") or "")[:16].replace("T", " ")
        project = s.get("project", "")
        provider = s.get("provider", "?")

        print(f"[{provider}] {dt}  {project}")
        print(f"  Turns: {turns}  |  Tokens: {tokens_in} in / {tokens_out} out"
              + (f"  |  Duration: {duration}" if duration else ""))
        print(f"  File: {s.get('file','')}")
        print()


def cmd_search(args):
    provider = args.provider
    kw = args.keyword

    providers_to_search = [provider] if provider else ["claude", "gemini"]
    results = []
    for p in providers_to_search:
        adapter = _get_adapter(p)
        if adapter:
            results.extend(adapter.search_sessions(kw, limit=10))

    if not results:
        print(f"No sessions found matching '{kw}'.")
        return

    print(f"Found {len(results)} session(s) matching '{kw}':\n")
    for s in results:
        dt = (s.get("start_time") or "")[:16].replace("T", " ")
        project = s.get("project", "")
        provider_name = s.get("provider", "?")
        print(f"[{provider_name}] {dt}  {project}")
        # Show matching snippet
        kw_lower = kw.lower()
        for msg in s.get("messages", []):
            content = msg.get("content", "")
            if kw_lower in content.lower():
                idx = content.lower().find(kw_lower)
                start = max(0, idx - 40)
                end = min(len(content), idx + 80)
                snippet = content[start:end].replace("\n", " ")
                print(f"  [{msg['role']}] ...{snippet}...")
                break
        print()


def cmd_export(args):
    sessions = _all_sessions(args.provider, limit=5)
    if not sessions:
        print("No sessions found.", file=sys.stderr)
        sys.exit(1)

    session = sessions[0]
    fmt = args.format

    if fmt == "markdown":
        dt = (session.get("start_time") or "")[:16].replace("T", " ")
        project = session.get("project", "")
        provider_name = session.get("provider", "?")
        print(f"# Session Log — {provider_name} — {dt}")
        print(f"\n**Project:** {project}")
        print(f"**Turns:** {session.get('turns', '?')}  |  "
              f"**Tokens:** {_fmt_number(session.get('input_tokens',0))} in / "
              f"{_fmt_number(session.get('output_tokens',0))} out\n")
        print("---\n")
        for msg in session.get("messages", []):
            role = msg.get("role", "?").upper()
            content = msg.get("content", "")
            print(f"**{role}:**")
            print(content)
            print()


def cmd_stats(args):
    sessions = _all_sessions(args.provider, limit=200)
    if not sessions:
        print("No sessions found.")
        return

    by_provider: dict[str, dict] = {}
    for s in sessions:
        p = s.get("provider", "unknown")
        if p not in by_provider:
            by_provider[p] = {"sessions": 0, "turns": 0, "input": 0, "output": 0}
        by_provider[p]["sessions"] += 1
        by_provider[p]["turns"] += s.get("turns", 0)
        by_provider[p]["input"] += s.get("input_tokens", 0)
        by_provider[p]["output"] += s.get("output_tokens", 0)

    print(f"Session Statistics ({len(sessions)} sessions total)\n")
    print(f"{'Provider':<12} {'Sessions':>8} {'Turns':>8} {'Input':>12} {'Output':>12}")
    print("─" * 56)
    for p, data in sorted(by_provider.items()):
        print(f"{p:<12} {data['sessions']:>8} {data['turns']:>8} "
              f"{_fmt_number(data['input']):>12} {_fmt_number(data['output']):>12}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Unified session log across AI providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--provider", choices=["claude", "gemini"],
                        help="Filter by provider")

    sub = parser.add_subparsers(dest="cmd")

    p_latest = sub.add_parser("--latest", help="Show recent sessions")
    p_latest.add_argument("--count", type=int, default=3)

    # Top-level flags as pseudo-subcommands
    parser.add_argument("--latest", action="store_true", help="Show recent sessions")
    parser.add_argument("--count", type=int, default=3, help="Number of sessions (with --latest)")
    parser.add_argument("--search", metavar="KEYWORD", help="Search session content")
    parser.add_argument("--export", choices=["markdown"], metavar="FORMAT",
                        help="Export latest session")
    parser.add_argument("--stats", action="store_true", help="Show session statistics")

    args = parser.parse_args()

    if args.search:
        args.keyword = args.search
        cmd_search(args)
    elif args.export:
        args.format = args.export
        cmd_export(args)
    elif args.stats:
        cmd_stats(args)
    else:
        # Default: show latest
        cmd_latest(args)


if __name__ == "__main__":
    main()
