#!/usr/bin/env python3
"""
ai_cost.py - Report and export cross-provider AI usage costs.
"""

from __future__ import annotations

import argparse
import json
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

from cost_tracker import CostTracker  # noqa: E402
from usage_importer import UsageImporter, sync_usage  # noqa: E402
from cli import command, set_result, CLIError, DATA_ERROR  # noqa: E402


def _format_money(value: float) -> str:
    return f"${value:,.4f}"


def _report_tracker(args):
    tracker = CostTracker()
    if not getattr(args, 'no_import', False):
        sync_usage(tracker)
    unpriced = sum(event.get('cost_usd') is None for event in tracker.load_events())
    if unpriced:
        print(f'Warning: {unpriced} usage record(s) have unknown prices; cost totals exclude them.',
              file=sys.stderr)
    return tracker


def cmd_period(args) -> None:
    tracker = _report_tracker(args)
    if args.command == "today":
        total = tracker.get_daily_cost()
        label = "today"
    elif args.command == "week":
        total = tracker.get_weekly_cost()
        label = "this week"
    else:
        total = tracker.get_monthly_cost()
        label = "this month"
    set_result({'period': args.command, 'cost_usd': total,
                'unpriced_events': sum(e.get('cost_usd') is None for e in tracker.load_events())})
    print(f"AI Cost - {label}")
    print("-" * 50)
    print(f"Total: {_format_money(total)}")


def cmd_breakdown(args) -> None:
    tracker = _report_tracker(args)
    breakdown = tracker.get_breakdown()
    set_result([{'provider': provider, 'model': model, **values}
                for (provider, model), values in sorted(breakdown.items())])
    print("AI Cost Breakdown")
    print("-" * 70)
    if not breakdown:
        print("No usage logged yet.")
        return
    for (provider, model), values in sorted(breakdown.items()):
        print(
            f"{provider:<10} {model:<24} "
            f"tokens:{values['total_tokens']:<10,} cost:{_format_money(values['cost_usd'])}"
        )


def cmd_export(args) -> None:
    tracker = _report_tracker(args)
    output = Path(args.output) if args.output else tracker.data_dir / "cost-report.csv"
    tracker.export_csv(output)
    set_result({'output': str(output), 'format': 'csv'})
    print(f"Exported CSV: {output}")


def cmd_budget(args) -> None:
    tracker = CostTracker() if args.budget_command == 'set' else _report_tracker(args)
    if args.budget_command == "set":
        tracker.set_budget("daily", args.amount)
        set_result(tracker.get_budgets())
        print(f"Daily budget set to {_format_money(args.amount)}")
    else:
        used, limit, exceeded = tracker.check_budget("daily")
        set_result({'used': used, 'limit': limit, 'exceeded': exceeded})
        print("AI Cost Budget")
        print("-" * 50)
        print(f"Used:  {_format_money(used)}")
        print(f"Limit: {_format_money(limit) if limit is not None else 'not set'}")
        print(f"State: {'exceeded' if exceeded else 'ok'}")


def cmd_log(args) -> None:
    tracker = CostTracker()
    event = tracker.log_usage(
        args.provider,
        args.model,
        args.input_tokens,
        args.output_tokens,
        session_id=args.session_id,
    )
    set_result(event)
    print(f"Logged usage for {event['provider']} / {event['model']}")
    print(f"Tokens: {event['total_tokens']:,}")
    print(f"Cost:   {_format_money(event['cost_usd'])}")


def cmd_import(args) -> None:
    result = UsageImporter(CostTracker()).import_usage(args.provider, args.source, args.dry_run)
    set_result(result)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print('Usage Import' + (' (dry run)' if args.dry_run else ''))
        print(f"New: {result['imported']}  Updated: {result['updated']}  Duplicates: {result['duplicates']}")
        print(f"Scanned files: {result['files_scanned']}  Unchanged: {result['files_unchanged']}")
        print(f"Unpriced records: {result['unpriced']}")
        print(f"Records outside scope or without project provenance: {result['skipped_scope']}")
        if result['backup']:
            print(f"Safety backup: {result['backup']}")
        for warning in result['warnings']:
            print(f'Warning: {warning}', file=sys.stderr)
    if result['warnings']:
        raise CLIError('Usage import was incomplete; inspect the warnings', DATA_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track and report AI usage cost")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("today", "week", "month"):
        period = sub.add_parser(name, help=f"Show cost for {name}")
        period.add_argument('--no-import', action='store_true', help='Use the existing cost log only')
        period.set_defaults(func=cmd_period)
    breakdown = sub.add_parser("breakdown", help="Show provider/model breakdown")
    breakdown.add_argument('--no-import', action='store_true')
    breakdown.set_defaults(func=cmd_breakdown)

    p_import = sub.add_parser('import', help='Import local Claude/Gemini session token usage')
    p_import.add_argument('--provider', choices=['claude', 'gemini'])
    p_import.add_argument('--source', type=Path, help='Session file or directory (requires --provider)')
    p_import.add_argument('--dry-run', action='store_true', help='Preview without writing data')
    p_import.add_argument('--json', action='store_true', help='Print a machine-readable report')
    p_import.set_defaults(func=cmd_import)

    p_export = sub.add_parser("export", help="Export usage as CSV")
    p_export.add_argument("--format", choices=["csv"], default="csv")
    p_export.add_argument("--output", help="Output CSV path")
    p_export.add_argument('--no-import', action='store_true')
    p_export.set_defaults(func=cmd_export)

    p_budget = sub.add_parser("budget", help="Manage the daily budget shortcut")
    sub_budget = p_budget.add_subparsers(dest="budget_command", required=True)
    p_budget_set = sub_budget.add_parser("set", help="Set the daily budget")
    p_budget_set.add_argument("amount", type=float)
    p_budget_set.set_defaults(func=cmd_budget)
    budget_status = sub_budget.add_parser("status", help="Show the daily budget")
    budget_status.add_argument('--no-import', action='store_true')
    budget_status.set_defaults(func=cmd_budget)

    p_log = sub.add_parser("log", help="Manually log usage")
    p_log.add_argument("--provider", required=True)
    p_log.add_argument("--model", required=True)
    p_log.add_argument("--input-tokens", type=int, required=True)
    p_log.add_argument("--output-tokens", type=int, required=True)
    p_log.add_argument("--session-id", help="Optional session identifier")
    p_log.set_defaults(func=cmd_log)
    return parser


@command(scoped=True)
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
