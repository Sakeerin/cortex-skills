"""Integration tests for prompt-lib/scripts/prompt_lib.py"""

import json
import sys
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
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


@pytest.mark.parametrize('incoming', [
    [], None, {'bad': {}}, {'bad': {'name': 'other', 'content': 'text'}},
    {'bad': {'name': 'bad', 'content': 1}},
    *[{'bad': {'name': 'bad', 'content': 'text', field: value}}
      for field, value in [('tags', 'tag'), ('tags', [1]), ('description', None),
                           ('created_at', 1), ('updated_at', [])]],
])
@pytest.mark.parametrize('existing', [False, True])
def test_invalid_import_is_atomic(data_dir, monkeypatch, capsys, incoming, existing):
    pl = _get_module(data_dir)
    destination = pl.get_prompts_file()
    if existing:
        pl.save_prompts({'old': {'name': 'old', 'content': 'keep'}})
    before = destination.read_bytes() if existing else None
    source = data_dir / 'import.json'
    if isinstance(incoming, dict):
        incoming = {'valid': {'name': 'valid', 'content': 'text'}, **incoming}
    source.write_text(json.dumps(incoming), encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['prompt-lib', '--json', 'import', str(source), '--overwrite'])
    with pytest.raises(SystemExit) as exc:
        pl.main()
    assert exc.value.code == 5
    result = json.loads(capsys.readouterr().out)
    assert result['error']['code'] == 'invalid_data'
    assert (destination.read_bytes() if destination.exists() else None) == before


@pytest.mark.parametrize('change', ['unrelated', 'modified', 'deleted'])
def test_editor_preserves_concurrent_changes(data_dir, monkeypatch, change):
    from cli import CLIError
    pl = _get_module(data_dir)
    pl.save_prompts({'edit': {'name': 'edit', 'content': 'original'}})

    def editor(command, **kwargs):
        def mutate():
            with pl.prompt_transaction() as prompts:
                if change == 'unrelated':
                    prompts['other'] = {'name': 'other', 'content': 'keep'}
                elif change == 'modified':
                    prompts['edit']['content'] = 'concurrent'
                else:
                    del prompts['edit']
        # A separate writer must finish while the editor is still open.
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(mutate).result(timeout=5)
        Path(command[1]).write_text('edited', encoding='utf-8')

    monkeypatch.setattr(pl.subprocess, 'run', editor)
    if change == 'unrelated':
        pl.cmd_edit(SimpleNamespace(name='edit'))
        assert pl.load_prompts()['edit']['content'] == 'edited'
        assert 'other' in pl.load_prompts()
    else:
        with pytest.raises(CLIError) as exc:
            pl.cmd_edit(SimpleNamespace(name='edit'))
        assert exc.value.exit_code == 4
        saved = pl.load_prompts()
        assert ('edit' not in saved if change == 'deleted'
                else saved['edit']['content'] == 'concurrent')


def test_import_skip_overwrite_and_bom(data_dir):
    pl = _get_module(data_dir)
    pl.save_prompts({'one': {'name': 'one', 'content': 'old'}})
    source = data_dir / 'import.json'
    source.write_text(json.dumps({'one': {'name': 'one', 'content': 'new'}}), encoding='utf-8-sig')
    pl.cmd_import(SimpleNamespace(file=str(source), overwrite=False))
    assert pl.load_prompts()['one']['content'] == 'old'
    pl.cmd_import(SimpleNamespace(file=str(source), overwrite=True))
    assert pl.load_prompts()['one']['content'] == 'new'
