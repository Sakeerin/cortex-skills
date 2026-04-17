"""Integration tests for prompt-lib/scripts/prompt_lib.py"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "prompt-lib" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "_lib"))


def _get_module(data_dir):
    import env_loader
    env_loader._loaded = False
    if "prompt_lib" in sys.modules:
        del sys.modules["prompt_lib"]
    import prompt_lib as pl
    pl.get_prompts_file = lambda: Path(data_dir) / "prompts.json"
    return pl


def _run(args, data_dir):
    pl = _get_module(data_dir)
    old_argv = sys.argv
    sys.argv = ["prompt-lib"] + args
    try:
        pl.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


def _load(data_dir):
    pl = _get_module(data_dir)
    return pl.load_prompts()


def test_add_prompt(data_dir):
    _run(["add", "test-prompt", "Hello {{name}}, you are {{role}}.", "--description", "Test"], data_dir)
    prompts = _load(data_dir)
    assert "test-prompt" in prompts
    assert prompts["test-prompt"]["content"] == "Hello {{name}}, you are {{role}}."
    assert prompts["test-prompt"]["description"] == "Test"


def test_add_duplicate_fails(data_dir, capsys):
    _run(["add", "dup-prompt", "Content 1"], data_dir)
    _run(["add", "dup-prompt", "Content 2"], data_dir)
    # Duplicate should be rejected — original content preserved
    prompts = _load(data_dir)
    assert prompts["dup-prompt"]["content"] == "Content 1"


def test_use_with_substitution(data_dir, capsys):
    _run(["add", "greet", "Hello {{name}}!"], data_dir)
    _run(["use", "greet", "--with", "name=World"], data_dir)
    out = capsys.readouterr().out
    assert "Hello World!" in out


def test_use_warns_unfilled_vars(data_dir, capsys):
    _run(["add", "tmpl", "Hello {{name}} from {{place}}"], data_dir)
    _run(["use", "tmpl", "--with", "name=Alice"], data_dir)
    out = capsys.readouterr().out
    err = capsys.readouterr().err
    # {{place}} should remain unfilled
    assert "{{place}}" in out or "place" in (out + err)


def test_delete_prompt(data_dir):
    _run(["add", "del-me", "Content"], data_dir)
    _run(["delete", "del-me"], data_dir)
    prompts = _load(data_dir)
    assert "del-me" not in prompts


def test_extract_vars():
    from prompt_lib import extract_vars
    vars_ = extract_vars("Hello {{name}}, review {{code}} in {{language}}")
    assert set(vars_) == {"name", "code", "language"}
