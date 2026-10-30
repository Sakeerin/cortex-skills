"""Isolation and machine-output contracts through real command processes."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cli import command, set_result
from data_scope import DataScope, current_scope, resolve_scope
from env_loader import get_data_dir


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    'todo': 'tasks', 'notes': 'notes', 'memory': 'memory', 'prompt-lib': 'prompt_lib',
    'ai-cost': 'ai_cost', 'ai-data': 'ai_data', 'token-budget': 'token_budget',
    'daily-report': 'daily_report', 'ai-provider': 'ai_provider', 'ai-context': 'ai_context',
    'ai-model-list': 'ai_model_list', 'ai-session-log': 'ai_session_log',
    'project-brief': 'project_brief', 'git-summary': 'git_summary',
    'env-check': 'env_check', 'skill-creator': 'skill_creator',
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    for key in list(os.environ):
        if key.startswith(('AI_', 'CLAUDE_', 'GOOGLE_', 'GEMINI_', 'OPENAI_', 'ANTHROPIC_', 'MISTRAL_')):
            monkeypatch.delenv(key)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    monkeypatch.setenv('AI_SKILLS_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('AI_USAGE_AUTO_IMPORT', '0')
    monkeypatch.setenv('AI_PROVIDER', 'ollama')
    monkeypatch.setenv('AI_MODEL', 'llama3')
    first, second = tmp_path / 'first', tmp_path / 'second'
    for project in (first, second):
        project.mkdir()
        (project / '.git').mkdir()
    return first, second


def run(skill, *args, cwd=None):
    return subprocess.run([sys.executable, '-B', str(ROOT / skill / 'scripts' / (SCRIPTS[skill] + '.py')),
                           *map(str, args)], cwd=cwd, capture_output=True, text=True, encoding='utf-8', timeout=30)


def machine(skill, *args, cwd=None, code=0):
    result = run(skill, *args, '--json', cwd=cwd)
    assert result.returncode == code, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload['schema_version'] == 1
    assert payload['exit_code'] == code
    assert payload['ok'] is (code == 0)
    assert payload['error'] is None if code == 0 else isinstance(payload['error'], dict)
    assert set(payload) == {'schema_version', 'ok', 'exit_code', 'scope', 'data', 'error', 'warnings'}
    assert result.stderr == ''
    return payload


@pytest.mark.parametrize('skill', SCRIPTS)
def test_every_python_skill_has_json_help_and_argument_errors(workspace, skill):
    help_result = machine(skill, '--help', cwd=workspace[0])
    assert '--json' in help_result['data']['text']
    invalid = machine(skill, '--not-a-real-option', cwd=workspace[0], code=2)
    assert invalid['error']['code'] == 'invalid_arguments'


@pytest.mark.parametrize('skill,add,list_args', [
    ('todo', ['add', '--title', 'isolated', '--project', 'label'], ['list', '--all']),
    ('notes', ['add', 'isolated'], ['list', '--all']),
    ('memory', ['add', 'same-key', 'isolated'], ['list']),
    ('prompt-lib', ['add', 'same-name', 'isolated'], ['list']),
])
def test_crud_scopes_do_not_inherit_or_leak(workspace, skill, add, list_args):
    first, second = workspace
    machine(skill, *add, '--scope', 'global', cwd=first)
    assert machine(skill, *list_args, '--scope', 'project', cwd=first)['data'] == []
    machine(skill, *add, '--scope', 'project', cwd=first)
    assert len(machine(skill, *list_args, '--scope', 'project', cwd=first)['data']) == 1
    assert machine(skill, *list_args, '--scope', 'project', cwd=second)['data'] == []
    session = ['--scope', 'session', '--scope-session', '../../sensitive/\u0e44\u0e17\u0e22']
    assert machine(skill, *list_args, *session, cwd=first)['data'] == []
    machine(skill, *add, *session, cwd=first)
    assert len(machine(skill, *list_args, *session, cwd=first)['data']) == 1
    assert machine(skill, *list_args, *session, cwd=second)['data'] == []
    assert len(machine(skill, *list_args, '--scope', 'global', cwd=second)['data']) == 1


def test_subdirectories_and_explicit_project_resolve_to_same_namespace(workspace):
    first, second = workspace
    nested = first / 'src'
    nested.mkdir()
    machine('memory', 'add', 'k', 'value', '--scope', 'project', cwd=first)
    assert machine('memory', 'get', 'k', '--scope', 'project', cwd=nested)['data']['value'] == 'value'
    selected = machine('memory', '--scope', 'project', '--scope-project', first,
                       'get', 'k', cwd=second)
    assert selected['data']['value'] == 'value'
    assert selected['scope']['project'] == os.path.normcase(str(first.resolve()))


def test_env_scope_and_explicit_global_override(workspace, monkeypatch):
    first, _ = workspace
    monkeypatch.setenv('AI_SKILLS_SCOPE', 'session')
    monkeypatch.setenv('AI_SKILLS_SESSION_ID', 'test-session')
    monkeypatch.setenv('AI_SKILLS_PROJECT_DIR', str(first))
    stored = machine('memory', 'add', 'k', 'v', cwd=first)
    assert stored['scope']['session'] == 'test-session'
    assert machine('memory', 'list', '--scope', 'global', cwd=first)['data'] == []


@pytest.mark.parametrize('flags', [
    ['--scope', 'session'], ['--scope', 'unknown'], ['--scope'],
    ['--scope-project', 'anything'], ['--scope-session', 's'],
    ['--scope', 'project', '--scope-session', 's'],
])
def test_scope_errors_are_json_usage_errors(workspace, flags):
    machine('memory', 'list', *flags, cwd=workspace[0], code=2)


def test_not_found_conflict_and_invalid_data_codes(workspace):
    first, _ = workspace
    for skill, args in [('todo', ['get', 'missing']), ('notes', ['done', 'missing']),
                        ('memory', ['get', 'missing']), ('prompt-lib', ['use', 'missing']),
                        ('project-brief', ['show'])]:
        assert machine(skill, *args, cwd=first, code=3)['error']['code'] == 'not_found'
        assert run(skill, *args, cwd=first).returncode == 3
    machine('prompt-lib', 'add', 'duplicate', 'hello', cwd=first)
    assert machine('prompt-lib', 'add', 'duplicate', 'hello', cwd=first, code=4)['error']['code'] == 'conflict'
    data = Path(os.environ['AI_SKILLS_DATA_DIR'])
    (data / 'prompts.json').write_text('{broken', encoding='utf-8')
    assert machine('prompt-lib', 'list', cwd=first, code=5)['error']['code'] == 'invalid_data'
    assert machine('env-check', '--provider', 'openai', cwd=first, code=6)['error']['code'] == 'unavailable'
    machine('ai-data', 'restore', first / 'missing.zip', cwd=first, code=3)
    machine('ai-cost', 'import', '--provider', 'claude', '--source', first / 'missing', cwd=first, code=3)
    (data / 'budget.json').write_text('{"daily": -1}', encoding='utf-8')
    machine('token-budget', 'status', cwd=first, code=5)
    assert json.loads((data / 'budget.json').read_text()) == {'daily': -1}
    machine('ai-cost', 'log', '--provider', 'openai', '--model', 'gpt-4o',
            '--input-tokens', '1', '--output-tokens', '0', cwd=first, code=5)
    assert not (data / 'cost-log.jsonl').exists()


def test_scoped_backup_restore_does_not_change_other_scopes(workspace):
    first, second = workspace
    flags = ['--scope', 'project']
    machine('memory', 'add', 'k', 'original', *flags, cwd=first)
    machine('memory', 'add', 'k', 'other', *flags, cwd=second)
    archive = machine('ai-data', 'backup', *flags, cwd=first)['data']['backup']
    machine('memory', 'add', 'k', 'changed', *flags, cwd=first)
    machine('ai-data', 'restore', archive, *flags, cwd=first, code=4)
    machine('ai-data', 'restore', archive, '--overwrite', *flags, cwd=first)
    assert machine('memory', 'get', 'k', *flags, cwd=first)['data']['value'] == 'original'
    assert machine('memory', 'get', 'k', *flags, cwd=second)['data']['value'] == 'other'
    assert machine('memory', 'list', '--scope', 'global', cwd=first)['data'] == []
    assert machine('ai-data', 'doctor', *flags, cwd=first)['data']['ok']


def test_session_scope_backup_and_data_root_override(workspace, tmp_path):
    first, _ = workspace
    flags = ['--scope', 'session', '--scope-session', 'a-session']
    machine('memory', 'add', 'k', 'original', *flags, cwd=first)
    archive = machine('ai-data', 'backup', *flags, cwd=first)['data']['backup']
    override = tmp_path / 'alternate'
    machine('ai-data', '--data-dir', override, 'restore', archive, *flags, cwd=first)
    selected = resolve_scope('session', str(first), 'a-session').directory(override)
    assert (selected / 'memory.jsonl').exists()
    assert not (override / 'memory.jsonl').exists()


def test_help_does_not_require_a_configured_session(workspace, monkeypatch):
    monkeypatch.setenv('AI_SKILLS_SCOPE', 'session')
    machine('memory', '--help', cwd=workspace[0])


def test_scoped_budget_session_identity_and_reset(workspace):
    first, _ = workspace
    flags = ['--scope', 'session', '--scope-session', 's1']
    machine('token-budget', 'set', 'session', '0.001', *flags, cwd=first)
    event = machine('ai-cost', 'log', '--provider', 'openai', '--model', 'gpt-4o',
                    '--input-tokens', '1000', '--output-tokens', '0', *flags, cwd=first)['data']
    assert event['session_id'] == 's1'
    status = machine('token-budget', 'status', *flags, cwd=first)['data']['budgets']
    assert status[1]['exceeded'] and status[1]['used'] == 0.0025
    machine('token-budget', 'reset', 'session', *flags, cwd=first)
    assert machine('token-budget', 'status', *flags, cwd=first)['data']['budgets'][1]['used'] == 0
    other = machine('token-budget', 'status', '--scope', 'session', '--scope-session', 's2', cwd=first)
    assert other['data']['budgets'][1]['limit'] is None
    machine('ai-cost', 'log', '--provider', 'openai', '--model', 'gpt-4o',
            '--input-tokens', '1', '--output-tokens', '0', '--session-id', 'wrong', *flags, cwd=first, code=2)


def usage(project, session, identity):
    return {'type': 'assistant', 'cwd': str(project), 'sessionId': session,
            'timestamp': '2026-10-30T08:00:00Z', 'message': {'id': identity, 'model': 'claude-sonnet-4-6',
            'usage': {'input_tokens': 100, 'output_tokens': 20}}}


def test_auto_import_filters_projects_and_sessions_and_explicit_cache(workspace, monkeypatch, tmp_path):
    first, second = workspace
    sources = tmp_path / 'sources'
    sources.mkdir()
    unowned = usage(first, 's1', 'unknown')
    unowned.pop('cwd')
    rows = [usage(first, 's1', 'a'), usage(first, 's2', 'b'), usage(second, 's1', 'c')]
    source = sources / 'session.jsonl'
    source.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    unknown_source = sources / 'unowned.jsonl'
    unknown_source.write_text(json.dumps(unowned) + '\n')
    monkeypatch.setenv('AI_CLAUDE_SESSION_DIR', str(sources))
    flags = ['--scope', 'session', '--scope-session', 's1']
    report = machine('ai-cost', 'import', '--provider', 'claude', *flags, cwd=first)['data']
    assert report['imported'] == 1 and report['skipped_scope'] == 3
    # Explicit source attributes unowned records to this project, but never
    # ignores the session filter. It cannot be skipped using the auto cache.
    report = machine('ai-cost', 'import', '--provider', 'claude', '--source', sources,
                      *flags, cwd=first)['data']
    assert report['imported'] == 1 and report['skipped_scope'] == 2
    project = machine('ai-cost', 'import', '--provider', 'claude', '--scope', 'project', cwd=first)['data']
    assert project['imported'] == 2
    assert machine('ai-cost', 'today', '--no-import', '--scope', 'project', cwd=second)['data']['cost_usd'] == 0
    assert machine('token-budget', 'status', *flags, cwd=first)['data']['budgets'][1]['used'] > 0


def test_common_runner_restores_context_and_preserves_literal_separator(workspace, monkeypatch, capsys):
    monkeypatch.chdir(workspace[0])
    argv = ['sample', '--json', '--scope', 'project', '--', '--scope-session', 'literal']
    monkeypatch.setattr(sys, 'argv', argv)

    @command(scoped=True)
    def sample():
        assert sys.argv[1:] == ['--', '--scope-session', 'literal']
        assert current_scope().kind == 'project'
        set_result({'path': get_data_dir()})

    assert sample() == 0
    assert sys.argv is argv
    assert current_scope().kind == 'global'
    assert json.loads(capsys.readouterr().out)['ok']


@pytest.mark.parametrize('value', [float('nan'), object()])
def test_nonserializable_result_still_emits_one_error_document(workspace, monkeypatch, capsys, value):
    monkeypatch.setattr(sys, 'argv', ['sample', '--json'])

    @command()
    def sample():
        set_result(value)

    with pytest.raises(SystemExit) as raised:
        sample()
    assert raised.value.code == 1
    assert json.loads(capsys.readouterr().out)['error']['code'] == 'operation_failed'


def test_scope_path_is_hashed_and_rejects_links(workspace, tmp_path):
    scope = DataScope('session', str(workspace[0]), '../../outside')
    root = tmp_path / 'data'
    selected = scope.directory(root)
    assert selected.is_relative_to(root)
    assert '..' not in selected.relative_to(root).parts
    root.mkdir(exist_ok=True)
    link = root / 'scopes'
    outside = tmp_path / 'outside'
    outside.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink creation needs privileges on Windows')
    with pytest.raises(ValueError, match='link'):
        scope.directory(root)


def test_project_resolution_does_not_change_process_cwd(workspace, monkeypatch):
    monkeypatch.chdir(workspace[0])
    scope = resolve_scope('project', str(workspace[1]))
    assert scope.project == os.path.normcase(str(workspace[1].resolve()))
    assert Path.cwd() == workspace[0]
