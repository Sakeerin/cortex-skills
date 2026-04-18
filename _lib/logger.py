#!/usr/bin/env python3
"""
logger.py — Simple ANSI-colored terminal output for AI Skills

Usage:
  from logger import info, success, warning, error, print_table
"""

import sys
import os

# Ensure emoji display correctly on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Disable colors if not a TTY or NO_COLOR is set
_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ

_RESET  = "\033[0m"  if _USE_COLOR else ""
_BOLD   = "\033[1m"  if _USE_COLOR else ""
_GREEN  = "\033[32m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_RED    = "\033[31m" if _USE_COLOR else ""
_CYAN   = "\033[36m" if _USE_COLOR else ""
_DIM    = "\033[2m"  if _USE_COLOR else ""


def info(msg: str) -> None:
    print(f"{_CYAN}ℹ{_RESET}  {msg}")


def success(msg: str) -> None:
    print(f"{_GREEN}✅{_RESET} {msg}")


def warning(msg: str) -> None:
    print(f"{_YELLOW}⚠️ {_RESET} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"{_RED}❌{_RESET} {msg}", file=sys.stderr)


def header(msg: str) -> None:
    print(f"\n{_BOLD}{msg}{_RESET}")
    print("─" * len(msg))


def dim(msg: str) -> None:
    print(f"{_DIM}{msg}{_RESET}")


def print_table(rows: list[tuple], headers: list[str] = None) -> None:
    """Print a simple aligned table."""
    if not rows:
        return

    all_rows = ([headers] + list(rows)) if headers else list(rows)
    col_widths = [max(len(str(cell)) for cell in col) for col in zip(*all_rows)]

    if headers:
        header_line = "  ".join(
            f"{_BOLD}{str(h):<{w}}{_RESET}" for h, w in zip(headers, col_widths)
        )
        print(header_line)
        print("─" * (sum(col_widths) + 2 * (len(col_widths) - 1)))

    for row in rows:
        print("  ".join(f"{str(cell):<{w}}" for cell, w in zip(row, col_widths)))
