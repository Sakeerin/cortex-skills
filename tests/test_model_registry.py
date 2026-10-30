"""Registry invariants, safe overrides and cross-skill consistency."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

import ai_provider
from cost_tracker import CostTracker
from errors import DataError, AmbiguousModelError
from model_registry import ModelRegistry, get_registry, validate_registry
from usage_importer import UsageImporter

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def registry(data_dir, monkeypatch):
    monkeypatch.delenv('AI_MODEL_REGISTRY', raising=False)
    rates = data_dir / 'legacy-rates.json'
    rates.write_text('{}')
    return ModelRegistry(override_path=data_dir / 'model-overrides.json', rate_path=rates)


def test_bundled_context_catalog_and_cost_share_one_source(registry, data_dir):
    rows = registry.list_models()
    assert len(rows) == 17
    tracker = CostTracker(data_dir)
    for row in rows:
        assert row['id'] in ai_provider.get_known_models(row['provider'])
        assert ai_provider.get_context_limit(row['id'], row['provider']) == row['context_window']
        assert tracker.has_rate(row['id'], row['provider']) is (row['rates'] is not None)
        if row['rates'] is not None:
            assert tracker.get_rate(row['id'], row['provider']) == row['rates']


def test_longest_boundary_match_and_unknown_context(registry):
    assert registry.rate('gpt-4o-mini-2024-07-18', 'openai')['input'] == 0.15
    assert registry.resolve('llama3.3:latest', 'ollama')['context_window'] == 128000
    for name in ['gpt-6', 'gpt-4ocean', 'claude-future', 'totally-unknown']:
        assert registry.resolve(name) is None
        assert ai_provider.get_context_limit(name) == 0
    assert registry.resolve('gpt-4o', 'claude') is None
    assert registry.rate('gpt-4o', 'claude') is None


def test_aliases_and_overrides_refresh_existing_instances(registry, monkeypatch):
    monkeypatch.setenv('AI_MODEL_REGISTRY', str(registry.override_path))
    shared = get_registry()
    assert shared.resolve('my-alias') is None
    registry.set_model('openai', 'my-custom', context_window=64000, aliases=['my-alias'],
                       rates={'input': 1, 'output': 2}, match_suffix=False)
    assert shared.resolve('MY-ALIAS')['id'] == 'my-custom'
    assert shared.resolve('my-custom-v2') is None
    assert ai_provider.get_context_limit('my-alias') == 64000
    assert shared.infer_provider('my-alias') == 'openai'
    registry.set_model('openai', 'my-custom', context_window=128000)
    assert shared.resolve('my-alias')['context_window'] == 128000
    assert shared.resolve('my-alias')['rates']['output'] == 2


def test_query_results_cannot_mutate_the_cache(registry):
    first = registry.resolve('gpt-4o')
    first['rates']['input'] = 999
    first['aliases'].append('bad')
    registry.list_models()[0]['context_window'] = 1
    assert registry.resolve('gpt-4o')['rates']['input'] == 2.5
    assert registry.resolve('bad') is None


def test_provider_collision_requires_disambiguation(registry):
    registry.set_model('ollama', 'gpt-4o', context_window=8192, rates={'input': 0, 'output': 0})
    with pytest.raises(AmbiguousModelError):
        registry.resolve('gpt-4o')
    assert registry.resolve('gpt-4o', 'openai')['context_window'] == 128000
    assert registry.resolve('gpt-4o', 'ollama')['context_window'] == 8192
    assert registry.infer_provider('gpt-4o') == 'unknown'


def test_duplicate_alias_does_not_replace_valid_file(registry):
    registry.set_model('openai', 'custom', context_window=1)
    original = registry.override_path.read_bytes()
    with pytest.raises(DataError, match='Duplicate'):
        registry.set_model('openai', 'other', aliases=['gpt-4o'])
    assert registry.override_path.read_bytes() == original


@pytest.mark.parametrize('field,value', [
    ('version', True), ('version', 2), ('models', {}), ('extra', 'unknown'),
])
def test_invalid_registry_top_level(field, value):
    document = {'version': 1, 'models': []}
    document[field] = value
    with pytest.raises(DataError):
        validate_registry(document)


@pytest.mark.parametrize('field,value', [
    ('context_window', -1), ('context_window', True), ('context_window', 1.2),
    ('provider', 'unsupported'), ('aliases', ['gpt-4o']), ('aliases', 'not-array'),
    ('match_suffix', 1), ('id', ' '), ('id', 'line\nbreak'),
    ('rates', {'input': -1, 'output': 0}), ('rates', {'input': True, 'output': 0}),
    ('rates', {'input': float('nan'), 'output': 0}),
    ('rates', {'input': float('inf'), 'output': 0}),
    ('rates', {'input': 10 ** 400, 'output': 0}), ('rates', {'input': 0}),
    ('rates', {'input': 0, 'output': 0, 'unknown': 1}),
])
def test_invalid_model_schema(registry, field, value):
    row = registry.resolve('gpt-4o')
    row[field] = value
    with pytest.raises(DataError):
        validate_registry({'version': 1, 'models': [row]})


def test_locality_does_not_follow_model_name_for_remote_pricing(registry, data_dir):
    assert registry.rate('anything', 'ollama') == {'input': 0, 'output': 0}
    assert registry.rate('llama-paid', 'openai') is None
    with pytest.raises(DataError, match='Local'):
        registry.set_model('ollama', 'paid', rates={'input': 1, 'output': 2})
    event = CostTracker(data_dir).log_usage('openai', 'llama-paid', 100, 20)
    assert event['cost_usd'] is None and event['pricing_status'] == 'unknown'


def test_legacy_prices_and_user_override_precedence(registry):
    registry.rate_path.write_text(json.dumps({'gpt-4o': {'input': 4, 'output': 5},
        'gpt-4o-mini-snapshot': {'input': 0.01, 'output': 0.02},
        'vendor-custom': {'input': 7, 'output': 8}}))
    assert registry.rate('gpt-4o', 'openai')['input'] == 4
    assert registry.rate('gpt-4o-mini-snapshot', 'openai')['input'] == 0.01
    assert registry.rate('vendor-custom', 'openai')['input'] == 7
    assert registry.rate_table()['vendor-custom']['output'] == 8
    registry.set_model('openai', 'gpt-4o', rates={'input': 1, 'output': 2})
    assert registry.rate('gpt-4o', 'openai')['input'] == 1
    registry.set_model('openai', 'gpt-4o', rates=None)
    assert registry.rate('gpt-4o', 'openai') is None


def test_ambiguous_legacy_price_does_not_leak_to_another_provider(registry):
    registry.rate_path.write_text(json.dumps({'gpt-4o': {'input': 4, 'output': 5}}))
    registry.set_model('ollama', 'gpt-4o', context_window=8192, rates={'input': 0, 'output': 0})
    assert registry.infer_provider('gpt-4o') == 'unknown'
    assert registry.rate('gpt-4o', 'openai')['input'] == 4
    assert registry.rate('gpt-4o', 'ollama')['input'] == 0
    assert registry.rate('gpt-4o', 'claude') is None


def test_remove_override_restores_builtin_and_rejects_builtin_deletion(registry):
    registry.set_model('openai', 'gpt-4o', context_window=9)
    registry.remove_model('openai', 'gpt-4o')
    assert registry.resolve('gpt-4o')['context_window'] == 128000
    with pytest.raises(FileNotFoundError):
        registry.remove_model('openai', 'gpt-4o')
    registry.set_model('openai', 'custom', context_window=5)
    registry.remove_model('openai', 'custom')
    assert registry.resolve('custom') is None


def test_corrupt_registry_does_not_fall_back_to_old_cached_data(registry):
    registry.set_model('openai', 'custom', context_window=5)
    registry.list_models()
    registry.override_path.write_text('{broken')
    with pytest.raises(DataError):
        registry.list_models()
    with pytest.raises(DataError):
        registry.infer_provider('custom')
    with pytest.raises(DataError):
        registry.rate('local-model', 'ollama')


def test_catalog_files_are_not_reparsed_for_each_price_lookup(registry, monkeypatch):
    import model_registry
    original = model_registry._read
    reads = []

    def read(path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(model_registry, '_read', read)
    for _ in range(30):
        assert registry.rate('gpt-4o', 'openai')['input'] == 2.5
        assert registry.resolve('gpt-4o')['context_window'] == 128000
    assert reads == [registry.builtin_path, registry.rate_path]


def test_manual_pricing_resolves_knownness_and_rate_once(data_dir, monkeypatch):
    tracker = CostTracker(data_dir)
    calls = []

    def changing_rate(*_args):
        calls.append(True)
        return None if len(calls) == 1 else {'input': 1, 'output': 2}

    monkeypatch.setattr(tracker.registry, 'rate', changing_rate)
    event = tracker.log_usage('openai', 'new-model', 1000, 100)
    assert event['cost_usd'] is None
    assert len(calls) == 1


def test_export_round_trip_and_protected_bundled_catalog(registry, tmp_path):
    document = registry.export()
    assert validate_registry(deepcopy(document), overrides=True) == document
    original = registry.builtin_path.read_bytes()
    protected = ModelRegistry(override_path=registry.builtin_path)
    with pytest.raises(ValueError, match='cannot overwrite'):
        protected.set_model('openai', 'anything', context_window=1)
    with pytest.raises(ValueError, match='cannot overwrite'):
        protected.remove_model('openai', 'gpt-4o')
    assert registry.builtin_path.read_bytes() == original


def test_registry_change_reprices_unchanged_imported_source(registry, data_dir, monkeypatch):
    monkeypatch.setenv('AI_MODEL_REGISTRY', str(registry.override_path))
    source = data_dir / 'source.jsonl'
    source.write_text(json.dumps({'type': 'assistant', 'sessionId': 's',
        'timestamp': '2026-10-30T08:00:00Z', 'message': {'id': 'm', 'model': 'custom-claude',
        'usage': {'input_tokens': 1000, 'output_tokens': 100}}}) + '\n')
    tracker = CostTracker(data_dir)
    importer = UsageImporter(tracker)
    importer.import_usage('claude', source)
    assert tracker.load_events()[0]['cost_usd'] is None
    assert importer.import_usage('claude', source)['files_unchanged'] == 1
    registry.set_model('claude', 'custom-claude', rates={'input': 1, 'output': 2})
    report = importer.import_usage('claude', source)
    assert report['updated'] == 1
    assert tracker.load_events()[0]['cost_usd'] == 0.0012
    assert report['backup']
