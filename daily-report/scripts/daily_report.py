#!/usr/bin/env python3
"""
daily_report.py — Auto-generate daily standup report from real data

Data sources: todo (tasks done/pending), git log (today's commits),
              ai-cost (token usage), notes (today's notes)

Usage:
  daily_report.py                    # report for today
  daily_report.py --yesterday        # report for yesterday
  daily_report.py --date YYYY-MM-DD  # specific date
  daily_report.py --format slack     # Slack format
  daily_report.py --format markdown  # Markdown format
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SKILL_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SKILL_DIR.parent / "_lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from env_loader import get_data_dir, get


# ---------------------------------------------------------------------------
# Data collectors
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Use 'id' for todo/notes, 'key' for memory
            eid = obj.get("id") or obj.get("key")
            if eid:
                if obj.get("deleted"):
                    entries.pop(eid, None)
                else:
                    entries[eid] = {**entries.get(eid, {}), **obj}
    return list(entries.values())


def collect_todos(target_date: str) -> tuple[list[str], list[str]]:
    """Return (done_today, still_pending) task titles."""
    data = get_data_dir()
    items = _load_jsonl(data / "todos.jsonl")

    done_today = []
    pending = []
    for t in items:
        updated = (t.get("updated_at") or "")[:10]
        created = (t.get("created_at") or "")[:10]
        if t.get("checked"):
            if updated == target_date:
                done_today.append(t.get("title", "?"))
        else:
            # Pending: created on or before target date
            if created <= target_date:
                pending.append(t.get("title", "?"))

    return done_today, pending


def collect_notes(target_date: str) -> list[str]:
    """Return note content created on target_date."""
    data = get_data_dir()
    items = _load_jsonl(data / "notes.jsonl")
    return [
        n.get("content", "")
        for n in items
        if n.get("date") == target_date and not n.get("done")
    ]


def collect_commits(target_date: str) -> list[str]:
    """Return commit subjects from git log on target_date."""
    try:
        since = f"{target_date} 00:00:00"
        until = f"{target_date} 23:59:59"
        result = subprocess.run(
            ["git", "log", f"--after={since}", f"--before={until}",
             "--format=%s (%h)", "--no-merges"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines
    except FileNotFoundError:
        return []


def collect_ai_cost(target_date: str) -> tuple[float, int, str]:
    """Return (total_cost_usd, total_tokens, provider_model) for target_date."""
    data = get_data_dir()
    cost_file = data / "cost-log.jsonl"
    if not cost_file.exists():
        return 0.0, 0, ""

    total_cost = 0.0
    total_tokens = 0
    models: dict[str, int] = {}

    with open(cost_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (obj.get("timestamp") or "")[:10] == target_date:
                total_cost += obj.get("cost_usd", 0)
                tokens = obj.get("input_tokens", 0) + obj.get("output_tokens", 0)
                total_tokens += tokens
                model_key = f"{obj.get('provider','?')}/{obj.get('model','?')}"
                models[model_key] = models.get(model_key, 0) + tokens

    top_model = max(models, key=models.get) if models else ""
    return total_cost, total_tokens, top_model


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _fmt_number(n: int) -> str:
    return f"{n:,}"


def render_default(report_date: str, done: list, pending: list,
                   commits: list, notes: list,
                   cost: float, tokens: int, model: str) -> str:
    lines = [f"Daily Report — {report_date}", "=" * 40]

    lines.append("\n✅ Done:")
    if done:
        for item in done:
            lines.append(f"  • {item}")
    else:
        lines.append("  (nothing marked done today)")

    lines.append("\n🔄 In Progress / Pending:")
    if pending:
        for item in pending[:5]:
            lines.append(f"  • {item}")
        if len(pending) > 5:
            lines.append(f"  • ... and {len(pending) - 5} more")
    else:
        lines.append("  (no pending tasks)")

    if commits:
        lines.append("\n📝 Commits:")
        for c in commits:
            lines.append(f"  • {c}")

    if notes:
        lines.append("\n🗒️  Notes:")
        for n in notes:
            lines.append(f"  • {n}")

    if tokens:
        lines.append(f"\n💰 AI Usage: {_fmt_number(tokens)} tokens"
                     + (f" — ${cost:.2f}" if cost else "")
                     + (f" ({model})" if model else ""))

    lines.append("\n🚧 Blockers: (none)")
    return "\n".join(lines)


def render_slack(report_date: str, done: list, pending: list,
                 commits: list, notes: list,
                 cost: float, tokens: int, model: str) -> str:
    lines = [f"📅 *Daily Report — {report_date}*", ""]

    lines.append("✅ *Done:*")
    if done:
        for item in done:
            lines.append(f"• ✅ {item}")
    else:
        lines.append("• (nothing marked done today)")

    lines.append("")
    lines.append("🔄 *In Progress:*")
    if pending:
        for item in pending[:5]:
            lines.append(f"• 🔄 {item}")
        if len(pending) > 5:
            lines.append(f"• ... and {len(pending) - 5} more")
    else:
        lines.append("• (no pending tasks)")

    if commits:
        lines.append("")
        lines.append("📝 *Commits:*")
        for c in commits:
            lines.append(f"• `{c}`")

    if notes:
        lines.append("")
        lines.append("🗒️  *Notes:*")
        for n in notes:
            lines.append(f"• {n}")

    if tokens:
        lines.append("")
        lines.append(f"💰 *AI Usage:* {_fmt_number(tokens)} tokens"
                     + (f" — ${cost:.2f}" if cost else "")
                     + (f" ({model})" if model else ""))

    lines.append("")
    lines.append("🚧 *Blockers:* ไม่มี")
    return "\n".join(lines)


def render_markdown(report_date: str, done: list, pending: list,
                    commits: list, notes: list,
                    cost: float, tokens: int, model: str) -> str:
    lines = [f"# Daily Report — {report_date}", ""]

    lines.append("## ✅ Done")
    if done:
        for item in done:
            lines.append(f"- [x] {item}")
    else:
        lines.append("- (nothing marked done today)")

    lines.append("")
    lines.append("## 🔄 In Progress")
    if pending:
        for item in pending[:5]:
            lines.append(f"- [ ] {item}")
        if len(pending) > 5:
            lines.append(f"- [ ] ... and {len(pending) - 5} more")
    else:
        lines.append("- (no pending tasks)")

    if commits:
        lines.append("")
        lines.append("## 📝 Commits")
        for c in commits:
            lines.append(f"- `{c}`")

    if notes:
        lines.append("")
        lines.append("## 🗒️ Notes")
        for n in notes:
            lines.append(f"- {n}")

    if tokens:
        lines.append("")
        lines.append("## 💰 AI Usage")
        lines.append(f"- Tokens: {_fmt_number(tokens)}")
        if cost:
            lines.append(f"- Cost: ${cost:.2f}")
        if model:
            lines.append(f"- Model: {model}")

    lines.append("")
    lines.append("## 🚧 Blockers")
    lines.append("None")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate daily standup report from todo, git, ai-cost, and notes data",
    )
    parser.add_argument("--yesterday", action="store_true", help="Report for yesterday")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Report for specific date")
    parser.add_argument(
        "--format", choices=["default", "slack", "markdown"], default="default",
        help="Output format (default: plain text)",
    )
    args = parser.parse_args()

    if args.date:
        try:
            date.fromisoformat(args.date)  # validates YYYY-MM-DD format
        except ValueError:
            print(f"Invalid date '{args.date}'. Use YYYY-MM-DD format.", file=sys.stderr)
            sys.exit(1)
        target_date = args.date
    elif args.yesterday:
        target_date = (date.today() - timedelta(days=1)).isoformat()
    else:
        target_date = date.today().isoformat()

    done, pending = collect_todos(target_date)
    notes = collect_notes(target_date)
    commits = collect_commits(target_date)
    cost, tokens, model = collect_ai_cost(target_date)

    renderers = {
        "default": render_default,
        "slack": render_slack,
        "markdown": render_markdown,
    }
    output = renderers[args.format](target_date, done, pending, commits, notes, cost, tokens, model)
    print(output)


if __name__ == "__main__":
    main()
