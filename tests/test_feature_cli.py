"""Forward tests for data maintenance and usage import through actual CLI processes."""

import json
from pathlib import Path
import subprocess
import sys

from file_lock import data_lock


ROOT = Path(__file__).resolve().parents[1]


def run_data(data_dir, *args):
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ai-data/scripts/ai_data.py'),
                           '--data-dir', str(data_dir), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def test_doctor_repair_restore_and_exit_codes(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    original = b'{"id":"a","title":"Task"}\nBROKEN\n{"id":"a","checked":true}\n'
    (data / 'todos.jsonl').write_bytes(original)
    backup = run_data(data, 'backup', '--json')
    assert backup.returncode == 0, backup.stderr
    archive = json.loads(backup.stdout)['backup']
    doctor = run_data(data, 'doctor', '--json')
    assert doctor.returncode == 1
    assert json.loads(doctor.stdout)['issues'][0]['line'] == 2
    repaired = run_data(data, 'doctor', '--repair', '--json')
    assert repaired.returncode == 0, repaired.stderr
    report = json.loads(repaired.stdout)
    assert report['ok'] and Path(report['backup']).exists()
    assert Path(report['quarantine'][0]).read_bytes() == b'BROKEN\n'
    repaired_bytes = (data / 'todos.jsonl').read_bytes()
    conflict = run_data(data, 'restore', archive, '--json')
    assert conflict.returncode == 1
    assert (data / 'todos.jsonl').read_bytes() == repaired_bytes
    preview = run_data(data, 'restore', archive, '--overwrite', '--dry-run', '--json')
    assert preview.returncode == 0
    assert (data / 'todos.jsonl').read_bytes() == repaired_bytes
    restored = run_data(data, 'restore', archive, '--overwrite', '--json')
    assert restored.returncode == 0, restored.stderr
    assert json.loads(restored.stdout)['backup']
    assert (data / 'todos.jsonl').read_bytes() == original


def test_restore_invalid_archive_does_not_claim_success(tmp_path):
    archive = tmp_path / 'broken.zip'
    archive.write_bytes(b'not zip')
    failed = run_data(tmp_path / 'data', 'restore', archive)
    assert failed.returncode == 1
    assert 'Restored:' not in failed.stdout
    assert 'Error:' in failed.stderr


def test_whole_json_document_requires_manual_recovery(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'prompts.json').write_text('{invalid')
    report = run_data(data, 'doctor', '--repair', '--json')
    assert report.returncode == 1
    assert (data / 'prompts.json').read_text() == '{invalid'


def test_real_lock_is_reentrant_and_excludes_another_process(tmp_path):
    code = ('import sys; from pathlib import Path; '
            f'sys.path.insert(0, {str(ROOT / "_lib")!r}); '
            'from file_lock import data_lock\n'
            'try:\n'
            ' with data_lock(Path(sys.argv[1]), timeout=0.1): print("acquired")\n'
            'except TimeoutError: print("busy")\n')
    with data_lock(tmp_path), data_lock(tmp_path):
        result = subprocess.run([sys.executable, '-B', '-c', code, str(tmp_path)],
                                capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'busy'
    result = subprocess.run([sys.executable, '-B', '-c', code, str(tmp_path)],
                            capture_output=True, text=True)
    assert result.stdout.strip() == 'acquired'


def test_simultaneous_imports_count_a_request_once(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    source = tmp_path / 'source.jsonl'
    source.write_text(json.dumps({'type': 'assistant', 'sessionId': 's',
        'timestamp': '2026-10-30T08:00:00Z', 'message': {
            'id': 'm', 'model': 'claude-sonnet-4-6',
            'usage': {'input_tokens': 100, 'output_tokens': 20}}}) + '\n')
    monkeypatch.setenv('AI_SKILLS_DATA_DIR', str(data))
    command = [sys.executable, '-B', str(ROOT / 'ai-cost/scripts/ai_cost.py'),
               'import', '--provider', 'claude', '--source', str(source), '--json']
    first = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    outputs = [first.communicate(timeout=30), second.communicate(timeout=30)]
    assert first.returncode == second.returncode == 0, outputs
    assert sum(json.loads(output)['imported'] for output, _ in outputs) == 1
    assert len((data / 'cost-log.jsonl').read_text().splitlines()) == 1
    assert not (data / 'budget.json').exists()


def test_import_with_unknown_price_is_visible_in_reports(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    source = tmp_path / 'source.jsonl'
    source.write_text(json.dumps({'type': 'assistant', 'sessionId': 's',
        'timestamp': '2026-10-30T08:00:00Z', 'message': {
            'id': 'm', 'model': 'unknown-model',
            'usage': {'input_tokens': 100, 'output_tokens': 20}}}) + '\n')
    monkeypatch.setenv('AI_SKILLS_DATA_DIR', str(data))
    imported = subprocess.run([sys.executable, '-B', str(ROOT / 'ai-cost/scripts/ai_cost.py'),
        'import', '--provider', 'claude', '--source', str(source)], capture_output=True, text=True)
    assert imported.returncode == 0, imported.stderr
    report = subprocess.run([sys.executable, '-B', str(ROOT / 'ai-cost/scripts/ai_cost.py'),
        'breakdown', '--no-import'], capture_output=True, text=True)
    assert report.returncode == 0, report.stderr
    assert 'unknown prices' in report.stderr
    assert 'unknown-model' in report.stdout
