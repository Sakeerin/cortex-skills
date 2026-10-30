"""Forward tests for central administration, legacy routing and wrappers."""

import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from data_scope import resolve_scope
from model_registry import ModelRegistry
import system_admin

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    home, project, data = tmp_path / 'home', tmp_path / 'project', tmp_path / 'data'
    home.mkdir()
    project.mkdir()
    (project / '.git').mkdir()
    for key in list(os.environ):
        if key.startswith(('AI_', 'CLAUDE_', 'GOOGLE_', 'GEMINI_', 'OPENAI_', 'ANTHROPIC_', 'MISTRAL_')):
            monkeypatch.delenv(key)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    monkeypatch.setenv('AI_SKILLS_DATA_DIR', str(data))
    monkeypatch.setenv('AI_USAGE_AUTO_IMPORT', '0')
    monkeypatch.setenv('AI_PROVIDER', 'openai')
    monkeypatch.setenv('AI_MODEL', 'gpt-4o')
    monkeypatch.chdir(project)
    return project, data


def run(*args):
    return subprocess.run([sys.executable, '-B', str(ROOT / 'cortex.py'), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8', timeout=30)


def machine(*args, code=0):
    result = run(*args, '--json')
    assert result.returncode == code, (result.stdout, result.stderr)
    assert result.stderr == ''
    report = json.loads(result.stdout)
    assert report['ok'] is (code == 0)
    assert report['exit_code'] == code
    assert report['schema_version'] == 1
    assert report['error'] is None if code == 0 else report['error']['message']
    return report


@pytest.mark.parametrize('arguments', [
    [], ['models'], ['skills'], ['provider'], ['data'], ['cost'], ['budget'], ['context'],
    ['run', 'todo'], ['models', 'set'], ['data', 'doctor'], ['run'], ['usage'],
])
def test_help_and_error_paths_remain_single_json_documents(workspace, arguments):
    result = machine(*arguments, '--help')
    assert 'usage:' in result['data']['text'].lower()
    machine(*arguments, '--invalid-option', code=2)


def test_status_and_doctor_are_offline_and_do_not_expose_keys(workspace, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'NEVER_EXPOSE_THIS_SECRET')
    monkeypatch.setenv('AI_USAGE_AUTO_IMPORT', '1')
    monkeypatch.setenv('AI_CLAUDE_SESSION_DIR', str(workspace[0] / 'missing-transcripts'))
    for command in ('status', 'doctor'):
        report = machine(command)
        assert 'NEVER_EXPOSE_THIS_SECRET' not in json.dumps(report)
    assert not (workspace[1] / 'cost-log.jsonl').exists()
    assert not (workspace[1] / 'usage-import-state.json').exists()
    assert machine('status')['data']['registry']['models'] == 17


def test_offline_helpers_never_invoke_provider_network(workspace, monkeypatch):
    import urllib.request

    def fail(*_args, **_kwargs):
        raise AssertionError('Network request made by offline admin command')

    monkeypatch.setattr(urllib.request, 'urlopen', fail)
    assert system_admin.status()['registry']['models'] == 17
    assert system_admin.doctor()['ok']


def test_skill_health_reports_bad_syntax_without_executing_code(workspace, monkeypatch):
    root = workspace[0] / 'installation'
    scripts = root / 'example' / 'scripts'
    scripts.mkdir(parents=True)
    (scripts.parent / 'SKILL.md').write_text('---\nname: example\n---\n## Usage\n## When to Use\n')
    (scripts.parent / 'example').write_text('wrapper')
    script = scripts / 'main.py'
    script.write_text('raise RuntimeError("do not execute")\n')
    monkeypatch.setattr(system_admin, 'ROOT', root)
    assert system_admin.validate_skill('example')['valid']
    script.write_text('def broken(:\n')
    report = system_admin.validate_skill('example')
    assert not report['valid'] and 'main.py' in report['errors'][0]


def test_configured_project_scope_requires_explicit_global_model_mutation(workspace, monkeypatch):
    monkeypatch.setenv('AI_SKILLS_SCOPE', 'project')
    machine('models', 'set', 'team', '--provider', 'openai', '--context', '100', code=2)
    machine('models', 'set', 'team', '--provider', 'openai', '--context', '100', '--scope', 'global')
    assert machine('models', 'show', 'team')['data']['context_window'] == 100
    assert machine('status')['data']['registry']['registry_scope'] == 'global'


def test_custom_model_is_shared_by_all_consumers(workspace):
    saved = machine('models', 'set', 'new-model', '--provider', 'openai', '--context', '64000',
                    '--input', '1', '--output', '2', '--alias', 'preferred')['data']
    assert saved['id'] == 'new-model'
    assert machine('models', 'show', 'preferred')['data']['context_window'] == 64000
    rows = machine('models', 'list', '--provider', 'openai', '--query', 'preferred')['data']
    assert [row['id'] for row in rows] == ['new-model']
    context = machine('context', '--model', 'preferred')['data']
    assert context['limit'] == 64000
    catalog = machine('run', 'ai-model-list', '--provider', 'openai', '--offline')['data']
    assert 'new-model' in [row['name'] for row in catalog['models']]
    provider = machine('provider', 'status')['data']
    assert 'new-model' in provider['known_models']
    logged = machine('cost', 'log', '--provider', 'openai', '--model', 'preferred',
                     '--input-tokens', '1000', '--output-tokens', '100')['data']
    assert logged['cost_usd'] == 0.0012


def test_model_override_removal_export_and_conflicts(workspace):
    machine('models', 'set', 'gpt-4o', '--provider', 'openai', '--context', '999')
    assert machine('models', 'show', 'gpt-4o')['data']['context_window'] == 999
    exported = workspace[0] / 'models.json'
    machine('models', 'export', '--overrides-only', '--output', exported)
    assert json.loads(exported.read_text())['models'][0]['context_window'] == 999
    machine('models', 'export', '--output', exported, code=4)
    machine('models', 'remove', 'gpt-4o', '--provider', 'openai')
    assert machine('models', 'show', 'gpt-4o')['data']['context_window'] == 128000
    machine('models', 'remove', 'gpt-4o', '--provider', 'openai', code=3)
    machine('models', 'show', 'missing', code=3)
    machine('models', 'set', 'gpt-4o', '--provider', 'ollama', '--context', '100')
    machine('models', 'show', 'gpt-4o', code=4)
    assert machine('models', 'show', 'gpt-4o', '--provider', 'ollama')['data']['context_window'] == 100
    # Default context/provider inspection already has an active provider and
    # must not become ambiguous when another provider registers the same ID.
    assert machine('context')['data']['limit'] == 128000
    assert machine('provider', 'status')['data']['provider'] == 'openai'


@pytest.mark.parametrize('arguments', [
    ['--context', '-1'], ['--input', '-1', '--output', '1'], ['--input', 'nan', '--output', '1'],
    ['--input', '1'], ['--unpriced', '--input', '1', '--output', '1'],
    ['--alias', 'gpt-4o'], ['--clear-aliases', '--alias', 'x'],
])
def test_invalid_metadata_does_not_modify_user_catalog(workspace, arguments):
    machine('models', 'set', 'existing', '--provider', 'openai', '--context', '1')
    path = workspace[1] / 'model-overrides.json'
    original = path.read_bytes()
    machine('models', 'set', 'bad', '--provider', 'openai', *arguments, code=2)
    assert path.read_bytes() == original


def test_forwarded_scopes_preserve_json_and_isolation(workspace):
    flags = ['--scope', 'session', '--scope-session', 'chat']
    machine('--scope', 'project', 'run', 'memory', 'add', 'key', 'project')
    machine('run', 'memory', 'add', 'key', 'session', *flags)
    assert machine('run', 'memory', 'get', 'key', *flags)['data']['value'] == 'session'
    assert machine('run', 'memory', 'get', 'key', '--scope', 'project')['data']['value'] == 'project'
    assert machine('run', 'memory', 'list')['data'] == []
    report = machine('status', *flags)
    assert report['scope']['session'] == 'chat'
    expected = resolve_scope('session', str(workspace[0]), 'chat').directory(workspace[1])
    assert Path(report['data']['data_dir']) == expected
    machine('models', 'set', 'not-project-local', '--provider', 'openai', '--context', '1',
            '--scope', 'project', code=2)
    assert not (workspace[1] / 'model-overrides.json').exists()
    machine('provider', 'status', '--scope', 'project', code=2)


def test_central_doctor_detects_corruption_and_repairs_only_selected_data(workspace):
    data = workspace[1]
    data.mkdir()
    (data / 'todos.jsonl').write_bytes(b'{"id":"a","title":"keep"}\nBROKEN\n')
    failed = machine('doctor', code=5)['data']
    assert not failed['data']['ok']
    repaired = machine('doctor', '--repair')['data']
    assert Path(repaired['data']['backup']).exists()
    assert Path(repaired['data']['quarantine'][0]).read_bytes() == b'BROKEN\n'
    assert (data / 'todos.jsonl').read_bytes() == b'{"id":"a","title":"keep"}\n'
    (data / 'model-overrides.json').write_text('{broken')
    report = machine('doctor', code=5)['data']
    assert not next(row for row in report['checks'] if row['name'] == 'registry')['ok']
    assert (data / 'model-overrides.json').read_text() == '{broken'


def test_registry_errors_have_machine_readable_results(workspace):
    data = workspace[1]
    data.mkdir()
    (data / 'model-overrides.json').write_text('{broken')
    for args in [('models', 'list'), ('models', 'validate'), ('status',)]:
        machine(*args, code=5)
    # Stored-cost reports remain usable for recovery without importing/repricing.
    assert machine('cost', 'today', '--no-import')['data']['cost_usd'] == 0


def test_skill_catalog_validation_and_safe_dispatch(workspace):
    rows = machine('skills', 'list')['data']
    assert len(rows) == 18
    assert next(row for row in rows if row['name'] == 'todo')['scoped']
    assert not next(row for row in rows if row['name'] == 'time')['python_cli']
    assert all(row['valid'] for row in machine('skills', 'validate', '--all')['data'])
    machine('skills', 'validate', 'missing', code=3)
    machine('skills', 'validate', '../outside', code=2)
    machine('skills', 'validate', code=2)
    machine('skills', 'validate', 'todo', '--all', code=2)
    machine('run', 'unknown', code=3)
    machine('run', 'sync-git', code=3)


def test_default_global_backup_contains_user_model_overrides(workspace):
    machine('models', 'set', 'custom', '--provider', 'openai', '--context', '1')
    backup = machine('data', 'backup')['data']['backup']
    with zipfile.ZipFile(backup) as archive:
        assert 'model-overrides.json' in archive.namelist()
    assert machine('data', 'doctor')['data']['ok']


def test_simultaneous_model_writes_keep_both_updates(workspace):
    prefix = [sys.executable, '-B', str(ROOT / 'cortex.py'), 'models', 'set']
    suffix = ['--provider', 'openai', '--context', '100', '--json']
    first = subprocess.Popen([*prefix, 'one', *suffix], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = subprocess.Popen([*prefix, 'two', *suffix], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    outputs = [first.communicate(timeout=30), second.communicate(timeout=30)]
    assert first.returncode == second.returncode == 0, outputs
    names = ModelRegistry().names('openai')
    assert 'one' in names and 'two' in names


@pytest.mark.skipif(os.name != 'nt', reason='Windows command wrapper')
def test_windows_wrapper_forwards_arguments_and_exit_status(workspace):
    for args, code in [(['status', '--json'], 0), (['models', 'show', 'missing', '--json'], 3)]:
        result = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/c', str(ROOT / 'cortex.cmd'), *args],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert result.returncode == code, (result.stdout, result.stderr)
        assert json.loads(result.stdout)['exit_code'] == code
