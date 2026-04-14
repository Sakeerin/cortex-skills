#!/usr/bin/env python3
"""
git_summary.py — Human-readable summary of git diff/log

Usage:
  git_summary.py                      # summarize unstaged changes
  git_summary.py --staged             # summarize staged changes
  git_summary.py --last N             # summarize last N commits
  git_summary.py --since DATE         # commits since date (e.g. yesterday, 2026-04-01)
  git_summary.py --branch BRANCH      # diff vs another branch
  git_summary.py --format prompt      # output ready for AI commit message generation
"""

import argparse
import subprocess
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


def run_git(*args, check=True) -> str:
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=check,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"git error: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("git not found. Please install git.", file=sys.stderr)
        sys.exit(1)


def parse_stat_line(line: str) -> tuple[str, int, int]:
    """Parse a line from git diff --stat. Returns (file, additions, deletions)."""
    # Example: " src/foo.py | 12 +++--"
    parts = line.strip().split("|")
    if len(parts) != 2:
        return line.strip(), 0, 0
    filename = parts[0].strip()
    changes = parts[1].strip()
    additions = changes.count("+")
    deletions = changes.count("-")
    return filename, additions, deletions


def get_diff_stats(diff_args: list[str]) -> list[tuple[str, int, int]]:
    """Return list of (file, +lines, -lines) from git diff --stat."""
    output = run_git("diff", "--stat", *diff_args, check=False)
    if not output:
        return []
    lines = output.splitlines()
    # Last line is summary (e.g. "3 files changed, 42 insertions(+), 7 deletions(-)")
    stats = []
    for line in lines[:-1]:
        if "|" in line:
            stats.append(parse_stat_line(line))
    return stats


def get_diff_numstat(diff_args: list[str]) -> list[tuple[str, int, int]]:
    """Return list of (file, additions, deletions) from git diff --numstat."""
    output = run_git("diff", "--numstat", *diff_args, check=False)
    if not output:
        return []
    stats = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            add_str, del_str, fname = parts
            try:
                adds = int(add_str) if add_str != "-" else 0
                dels = int(del_str) if del_str != "-" else 0
                stats.append((fname, adds, dels))
            except ValueError:
                pass
    return stats


def format_file_changes(stats: list[tuple[str, int, int]]) -> str:
    if not stats:
        return "  (no changes)"
    lines = []
    for fname, adds, dels in stats:
        parts = []
        if adds:
            parts.append(f"+{adds}")
        if dels:
            parts.append(f"-{dels}")
        suffix = f" ({', '.join(parts)})" if parts else ""
        lines.append(f"  - {fname}{suffix}")
    return "\n".join(lines)


def get_log_entries(log_args: list[str]) -> list[dict]:
    sep = "|||"
    fmt = f"%H{sep}%s{sep}%an{sep}%ad{sep}%D"
    output = run_git("log", f"--format={fmt}", "--date=short", *log_args, check=False)
    if not output:
        return []
    entries = []
    for line in output.splitlines():
        parts = line.split(sep)
        if len(parts) >= 4:
            entries.append({
                "hash": parts[0][:8],
                "subject": parts[1],
                "author": parts[2],
                "date": parts[3],
                "refs": parts[4] if len(parts) > 4 else "",
            })
    return entries


# ---------------------------------------------------------------------------
# Summary modes
# ---------------------------------------------------------------------------

def summarize_diff(diff_args: list[str], label: str, fmt: str):
    stats = get_diff_numstat(diff_args)

    if fmt == "prompt":
        if not stats:
            print("No changes to summarize.")
            return
        total_files = len(stats)
        total_adds = sum(a for _, a, _ in stats)
        total_dels = sum(d for _, _, d in stats)
        print(f"Please write a conventional commit message for these changes:\n")
        print(f"Files changed ({total_files}):")
        for fname, adds, dels in stats:
            parts = []
            if adds:
                parts.append(f"+{adds}")
            if dels:
                parts.append(f"-{dels}")
            suffix = f" ({', '.join(parts)})" if parts else ""
            print(f"- {fname}{suffix}")
        print(f"\nSummary: {total_adds} insertions(+), {total_dels} deletions(-)")
    else:
        if not stats:
            print(f"{label}: no changes.")
            return
        total_adds = sum(a for _, a, _ in stats)
        total_dels = sum(d for _, _, d in stats)
        print(f"{label}  ({total_adds} insertions, {total_dels} deletions)")
        print(format_file_changes(stats))


def summarize_log(log_args: list[str], fmt: str):
    entries = get_log_entries(log_args)

    if not entries:
        print("No commits found.")
        return

    if fmt == "prompt":
        print(f"Here are the recent commits ({len(entries)} total):\n")
        for e in entries:
            print(f"- [{e['hash']}] {e['date']} — {e['subject']} ({e['author']})")
    else:
        for e in entries:
            refs = f"  ({e['refs']})" if e["refs"] else ""
            print(f"  [{e['hash']}] {e['date']}  {e['subject']}{refs}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Human-readable git diff/log summary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="Summarize staged changes")
    group.add_argument("--last", type=int, metavar="N", help="Summarize last N commits")
    group.add_argument("--since", metavar="DATE", help="Commits since date (e.g. yesterday, 2026-04-01)")
    group.add_argument("--branch", metavar="BRANCH", help="Diff vs another branch")

    parser.add_argument(
        "--format", choices=["default", "prompt"], default="default",
        help="Output format: 'default' or 'prompt' (for AI commit message generation)",
    )

    args = parser.parse_args()
    fmt = args.format

    if args.last:
        summarize_log([f"-{args.last}"], fmt)
    elif args.since:
        summarize_log([f"--since={args.since}"], fmt)
    elif args.staged:
        summarize_diff(["--cached"], "Staged changes", fmt)
    elif args.branch:
        current = run_git("rev-parse", "--abbrev-ref", "HEAD")
        summarize_diff([f"{args.branch}...{current}"], f"Diff vs {args.branch}", fmt)
    else:
        # Default: unstaged changes
        summarize_diff([], "Unstaged changes", fmt)


if __name__ == "__main__":
    main()
