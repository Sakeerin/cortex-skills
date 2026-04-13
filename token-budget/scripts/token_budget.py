#!/usr/bin/env python3
"""
token_budget.py - Manage daily, session, and monthly cost budgets.
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

from cost_tracker import CostTracker

BUDGET_TYPES = ("daily", "session", "monthly")


def _format_money(value: float | None) -> str:
    if value is None:
        return "not set"
    return f"${value:,.4f}"


def cmd_set(args) -> None:
    tracker = CostTracker()
    tracker.set_budget(args.kind, args.amount)
    print(f"Set {args.kind} budget to {_format_money(args.amount)}")


def cmd_status(_args) -> None:
    tracker = CostTracker()
    budgets = tracker.get_budgets()
    print("Token Budget Status")
    print("-" * 60)
    for kind in BUDGET_TYPES:
        used, limit, exceeded = tracker.check_budget(kind)
        threshold = float(budgets.get("alert_threshold", 80))
        pct = (used / limit * 100) if limit else 0.0
        alert = "alert" if limit and pct >= threshold else "ok"
        if exceeded:
            alert = "exceeded"
        suffix = f" ({pct:.1f}%)" if limit else ""
        print(
            f"{kind:<8} used:{_format_money(used):<12} "
            f"limit:{_format_money(limit):<12} state:{alert}{suffix}"
        )
    print(f"Alert threshold: {budgets.get('alert_threshold', 80)}%")


def cmd_reset(args) -> None:
    tracker = CostTracker()
    tracker.reset_budget(args.kind)
    if args.kind == "session":
        print("Reset session spend to $0.0000")
    else:
        print(f"Cleared {args.kind} budget")


def cmd_alert(args) -> None:
    tracker = CostTracker()
    tracker.set_alert_threshold(args.threshold)
    print(f"Alert threshold set to {args.threshold}%")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage AI token and cost budgets")
    sub = parser.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set", help="Set a budget")
    p_set.add_argument("kind", choices=BUDGET_TYPES)
    p_set.add_argument("amount", type=float)
    p_set.set_defaults(func=cmd_set)

    sub.add_parser("status", help="Show budget usage").set_defaults(func=cmd_status)

    p_reset = sub.add_parser("reset", help="Reset or clear a budget")
    p_reset.add_argument("kind", choices=BUDGET_TYPES)
    p_reset.set_defaults(func=cmd_reset)

    p_alert = sub.add_parser("alert", help="Set alert threshold percent")
    p_alert.add_argument("--threshold", type=int, required=True)
    p_alert.set_defaults(func=cmd_alert)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
