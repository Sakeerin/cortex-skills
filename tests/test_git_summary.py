"""Integration tests for git-summary/scripts/git_summary.py"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "git-summary" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_module():
    if "git_summary" in sys.modules:
        del sys.modules["git_summary"]
    import git_summary as gs
    return gs


def test_parse_stat_line():
    gs = _get_module()
    fname, adds, dels = gs.parse_stat_line(" app/foo.py | 12 +++--")
    assert fname == "app/foo.py"
    assert adds == 3
    assert dels == 2


def test_format_file_changes_empty():
    gs = _get_module()
    result = gs.format_file_changes([])
    assert "no changes" in result


def test_format_file_changes():
    gs = _get_module()
    result = gs.format_file_changes([("app/foo.py", 10, 2), ("app/bar.py", 0, 5)])
    assert "app/foo.py" in result
    assert "+10" in result
    assert "-2" in result
    assert "app/bar.py" in result


def test_run_in_real_repo(capsys):
    """Run git-summary --last 1 against the real cortex-skills repo."""
    gs = _get_module()
    import os
    old_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    old_argv = sys.argv
    sys.argv = ["git-summary", "--last", "1"]
    try:
        gs.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    out = capsys.readouterr().out
    # Should show at least one commit entry
    assert "[" in out  # commit hash in brackets


def test_format_prompt(capsys):
    gs = _get_module()
    import os
    old_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    old_argv = sys.argv
    sys.argv = ["git-summary", "--last", "2", "--format", "prompt"]
    try:
        gs.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    out = capsys.readouterr().out
    assert "commits" in out.lower()
