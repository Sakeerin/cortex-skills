"""Usage import contracts: deduplication, streaming, pricing and CLI integration."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from cost_tracker import CostTracker
from usage_importer import UsageImporter


def claude(identity='msg-1', output=20, model='claude-sonnet-4-6', **usage):
    return {'type': 'assistant', 'sessionId': 'session-a',
            'timestamp': '2026-10-30T08:00:00+07:00',
            'message': {'id': identity, 'model': model,
                        'content': [{'type': 'text', 'text': 'PRIVATE_TRANSCRIPT'}],
                        'usage': {'input_tokens': 100, 'output_tokens': output, **usage}}}


def write_lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return path


@pytest.fixture
def importer(data_dir):
    return UsageImporter(CostTracker(data_dir))


def test_import_is_idempotent_and_skips_unchanged_files(importer, tmp_path):
    source = write_lines(tmp_path / 'sessions/session.jsonl', [claude()])
    first = importer.import_usage('claude', source)
    second = importer.import_usage('claude', source)
    assert first['imported'] == 1
    assert second['imported'] == second['updated'] == 0
    assert second['files_unchanged'] == 1
    event = importer.tracker.load_events()[0]
    assert event['timestamp'] == '2026-10-30T08:00:00+07:00'
    assert event['input_tokens'] == 100
    assert event['cost_usd'] == pytest.approx(0.0006)
    assert 'PRIVATE_TRANSCRIPT' not in importer.tracker.log_path.read_text()


def test_streaming_updates_one_request_and_backs_up_previous_log(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [claude(output=1)])
    importer.import_usage('claude', source)
    write_lines(source, [claude(output=1), claude(output=40)])
    report = importer.import_usage('claude', source)
    assert report['updated'] == 1
    assert Path(report['backup']).is_file()
    events = importer.tracker.load_events()
    assert len(events) == 1
    assert events[0]['output_tokens'] == 40
    assert not importer.tracker.budget_path.exists()


def test_copied_transcripts_do_not_double_count(importer, tmp_path):
    folder = tmp_path / 'sessions'
    original = write_lines(folder / 'one.jsonl', [claude()])
    shutil.copyfile(original, folder / 'two.jsonl')
    report = importer.import_usage('claude', folder)
    assert report['imported'] == 1
    assert len(importer.tracker.load_events()) == 1


def test_reimporting_a_copy_does_not_rewrite_log_or_create_backups(importer, tmp_path):
    first = write_lines(tmp_path / 'one.jsonl', [claude()])
    copied = write_lines(tmp_path / 'two.jsonl', [claude()])
    importer.import_usage('claude', first)
    original = importer.tracker.log_path.read_bytes()
    for source in (copied, first, copied):
        source.touch()
        report = importer.import_usage('claude', source)
        assert report['updated'] == report['imported'] == 0
        assert report['backup'] is None
    assert importer.tracker.log_path.read_bytes() == original


def test_new_session_with_same_message_id_is_distinct(importer, tmp_path):
    other = claude()
    other['sessionId'] = 'session-b'
    source = write_lines(tmp_path / 'session.jsonl', [claude(), other])
    assert importer.import_usage('claude', source)['imported'] == 2


def test_dry_run_creates_no_ledger_backup_or_import_state(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [claude()])
    assert importer.import_usage('claude', source, dry_run=True)['imported'] == 1
    assert not importer.tracker.log_path.exists()
    assert not importer.state_path.exists()
    assert not (importer.tracker.data_dir / 'backups').exists()


def test_unknown_model_keeps_tokens_with_explicit_unknown_price(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [claude(model='future-model')])
    report = importer.import_usage('claude', source)
    event = importer.tracker.load_events()[0]
    assert report['unpriced'] == 1
    assert event['cost_usd'] is None
    assert event['pricing_status'] == 'unknown'
    assert importer.tracker.get_daily_cost() == 0
    assert importer.tracker.get_breakdown()[('claude', 'future-model')]['unpriced_events'] == 1


def test_cache_tokens_are_preserved_and_not_priced_at_uncached_rate(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [claude(cache_read_input_tokens=200,
                                                          cache_creation_input_tokens=50)])
    importer.import_usage('claude', source)
    event = importer.tracker.load_events()[0]
    assert event['input_tokens'] == 350
    assert event['metadata']['cache_read_tokens'] == 200
    assert event['metadata']['cache_write_tokens'] == 50
    assert event['cost_usd'] is None


def test_user_supplied_cache_prices_and_specific_snapshot_match(importer, tmp_path):
    rates = tmp_path / 'rates.json'
    rates.write_text(json.dumps({'claude-sonnet-4-6': {
        'input': 3, 'output': 15, 'cache_read': 0.3, 'cache_write': 3.75}}))
    importer.tracker.rate_path = rates
    source = write_lines(tmp_path / 'session.jsonl', [claude(model='claude-sonnet-4-6-20261001',
                                                          cache_read_input_tokens=1000)])
    importer.import_usage('claude', source)
    assert importer.tracker.load_events()[0]['cost_usd'] == pytest.approx(0.0009)
    assert importer.tracker.get_rate('gpt-4o-mini-2024-07-18', 'openai')['input'] == 0.15


def test_gemini_json_document_and_thought_tokens(importer, tmp_path):
    source = tmp_path / 'session-gemini.json'
    source.write_text(json.dumps({'sessionId': 'gemini-session', 'messages': [
        {'id': 'user', 'type': 'user', 'content': 'PRIVATE_TRANSCRIPT'},
        {'id': 'reply', 'type': 'gemini', 'timestamp': '2026-10-30T01:00:00Z',
         'model': 'gemini-2.5-flash', 'tokens': {'input': 100, 'output': 10, 'thoughts': 5}}
    ]}), encoding='utf-8')
    assert importer.import_usage('gemini', source)['imported'] == 1
    event = importer.tracker.load_events()[0]
    assert event['session_id'] == 'gemini-session'
    assert event['output_tokens'] == 15
    assert event['metadata']['reasoning_tokens'] == 5


def test_gemini_jsonl_header_and_repeated_token_updates(importer, tmp_path):
    message = {'id': 'reply', 'type': 'gemini', 'model': 'gemini-2.5-flash',
               'timestamp': '2026-10-30T01:00:00Z'}
    with_tokens = {**message, 'tokens': {'input': 100, 'output': 20}}
    source = write_lines(tmp_path / 'session-gemini.jsonl', [
        {'sessionId': 'gemini-session', 'projectHash': 'proj'}, message, with_tokens])
    assert importer.import_usage('gemini', source)['imported'] == 1
    assert importer.tracker.load_events()[0]['session_id'] == 'gemini-session'


def test_gemini_cache_redistribution_preserves_coherent_input_totals(importer, tmp_path):
    rates = tmp_path / 'rates.json'
    rates.write_text(json.dumps({'gemini-2.5-pro': {'input': 1, 'output': 1, 'cache_read': 0.1}}))
    importer.tracker.rate_path = rates
    row = {'id': 'reply', 'type': 'gemini', 'model': 'gemini-2.5-pro',
           'timestamp': '2026-10-30T01:00:00Z', 'tokens': {'input': 2000, 'output': 250}}
    source = write_lines(tmp_path / 'session.jsonl', [row])
    importer.import_usage('gemini', source)
    row['tokens']['cached'] = 1000
    write_lines(source, [row])
    report = importer.import_usage('gemini', source)
    assert report['updated'] == 1
    event = importer.tracker.load_events()[0]
    assert event['metadata']['input_uncached_tokens'] == 1000
    assert event['metadata']['cache_read_tokens'] == 1000
    assert event['input_tokens'] == 2000
    assert event['cost_usd'] == pytest.approx(0.00135)


def test_claude_server_tool_requests_leave_price_explicitly_unknown(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [
        claude(server_tool_use={'web_search_requests': 2})])
    report = importer.import_usage('claude', source)
    event = importer.tracker.load_events()[0]
    assert report['unpriced'] == 1
    assert event['metadata']['server_tool_requests']['web_search_requests'] == 2
    assert event['pricing_status'] == 'unknown'
    assert event['cost_usd'] is None


def test_legacy_gemini_usage_metadata(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [{
        'id': 'm', 'role': 'model', 'model': 'gemini-2.5-pro',
        'timestamp': '2026-10-30T01:00:00Z',
        'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 10,
                          'cachedContentTokenCount': 20}}])
    importer.import_usage('gemini', source)
    event = importer.tracker.load_events()[0]
    assert event['input_tokens'] == 100
    assert event['metadata']['input_uncached_tokens'] == 80
    assert event['cost_usd'] is None


def test_incomplete_line_retries_without_counting_valid_rows_twice(importer, tmp_path):
    source = write_lines(tmp_path / 'session.jsonl', [claude()])
    with source.open('a', encoding='utf-8') as handle:
        handle.write('{"type":')
    first = importer.import_usage('claude', source)
    assert first['warnings']
    write_lines(source, [claude(), claude(identity='msg-2')])
    second = importer.import_usage('claude', source)
    assert second['imported'] == 1
    assert len(importer.tracker.load_events()) == 2


@pytest.mark.parametrize('change', [
    {'input_tokens': -1}, {'input_tokens': True}, {'output_tokens': 1.5}
])
def test_invalid_counts_are_reported_and_not_imported(importer, tmp_path, change):
    source = write_lines(tmp_path / 'session.jsonl', [claude(**change)])
    report = importer.import_usage('claude', source)
    assert report['warnings']
    assert report['imported'] == 0


def test_invalid_existing_cost_log_requires_doctor(importer, tmp_path):
    importer.tracker.log_path.write_text('CORRUPTED\n')
    source = write_lines(tmp_path / 'session.jsonl', [claude()])
    with pytest.raises(ValueError, match='doctor'):
        importer.import_usage('claude', source)
    assert importer.tracker.log_path.read_text() == 'CORRUPTED\n'


def test_invalid_existing_cost_schema_requires_doctor(importer, tmp_path):
    importer.tracker.log_usage('openai', 'gpt-4o', 100, 20)
    event = importer.tracker.load_events()[0]
    event['input_tokens'] = -1
    original = json.dumps(event) + '\n'
    importer.tracker.log_path.write_text(original)
    source = write_lines(tmp_path / 'session.jsonl', [claude()])
    with pytest.raises(ValueError, match='doctor'):
        importer.import_usage('claude', source)
    assert importer.tracker.log_path.read_text() == original


@pytest.mark.parametrize('metadata', [None, [], {'cache_read_tokens': 'BROKEN'}])
def test_invalid_existing_metadata_is_reported_by_doctor_and_blocks_import(importer, tmp_path, metadata):
    from data_manager import DataManager
    source = write_lines(tmp_path / 'session.jsonl', [claude()])
    importer.import_usage('claude', source)
    event = importer.tracker.load_events()[0]
    event['metadata'] = metadata
    importer.tracker.log_path.write_text(json.dumps(event) + '\n')
    assert not DataManager(importer.tracker.data_dir).doctor()['ok']
    with pytest.raises(ValueError, match='doctor'):
        importer.import_usage('claude', source)


def test_missing_source_and_ambiguous_provider_are_rejected(importer, tmp_path):
    with pytest.raises(ValueError, match='requires'):
        importer.import_usage(source=tmp_path)
    with pytest.raises(ValueError, match='not found'):
        importer.import_usage('claude', tmp_path / 'missing')


def test_external_log_append_is_not_hidden_by_tracker_cache(importer, tmp_path):
    tracker = importer.tracker
    tracker.log_usage('openai', 'gpt-4o', 1, 1)
    tracker.load_events()
    CostTracker(tracker.data_dir).log_usage('openai', 'gpt-4o', 2, 2)
    tracker.log_usage('openai', 'gpt-4o', 3, 3)
    assert len(tracker.load_events()) == 3


def test_reporting_cli_auto_import_and_opt_out(importer, tmp_path, monkeypatch):
    folder = tmp_path / 'sessions'
    write_lines(folder / 'session.jsonl', [claude()])
    monkeypatch.setenv('AI_CLAUDE_SESSION_DIR', str(folder))
    monkeypatch.setenv('AI_GEMINI_SESSION_DIR', str(tmp_path / 'empty'))
    monkeypatch.setenv('AI_USAGE_AUTO_IMPORT', '1')
    script = Path(__file__).resolve().parents[1] / 'ai-cost/scripts/ai_cost.py'
    command = [sys.executable, '-B', str(script), 'today']
    skipped = subprocess.run(command + ['--no-import'], capture_output=True, text=True)
    assert skipped.returncode == 0, skipped.stderr
    assert not importer.tracker.log_path.exists()
    imported = subprocess.run(command, capture_output=True, text=True)
    assert imported.returncode == 0, imported.stderr
    assert len(importer.tracker.load_events()) == 1
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode == 0
    assert len(importer.tracker.load_events()) == 1


def test_default_gemini_discovery_does_not_read_credentials(importer, tmp_path, monkeypatch):
    monkeypatch.setenv('AI_GEMINI_SESSION_DIR', str(tmp_path))
    (tmp_path / 'oauth_creds.json').write_text('not a session')
    report = importer.import_usage('gemini')
    assert report['files_scanned'] == 0
    assert not report['warnings']
