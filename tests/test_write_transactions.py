"""Deterministic interleaving tests: a second writer cannot read stale state."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import SimpleNamespace

import pytest

from cost_tracker import CostTracker
from test_prompt_lib import _get_module


def assert_serialized(monkeypatch, owner, reader_name, first, second):
    original = getattr(owner, reader_name)
    first_read = Event()
    release = Event()
    second_started = Event()
    second_read = Event()
    guard = Lock()
    calls = 0

    def read():
        nonlocal calls
        with guard:
            calls += 1
            number = calls
        value = original()
        if number == 1:
            first_read.set()
            assert release.wait(5)
        else:
            second_read.set()
        return value

    def run_second():
        second_started.set()
        return second()

    monkeypatch.setattr(owner, reader_name, read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        try:
            assert first_read.wait(5)
            b = pool.submit(run_second)
            assert second_started.wait(5)
            assert not second_read.wait(0.2), 'Second writer read outside transaction lock'
        finally:
            release.set()
        a.result(timeout=5)
        b.result(timeout=5)


@pytest.mark.parametrize('operation', ['set', 'threshold', 'reset', 'spend'])
def test_budget_mutations_are_transactions(data_dir, monkeypatch, operation):
    tracker = CostTracker(data_dir)
    tracker.set_budget('monthly', 30)
    actions = {
        'set': lambda: tracker.set_budget('daily', 12),
        'threshold': lambda: tracker.set_alert_threshold(90),
        'reset': lambda: tracker.reset_budget('monthly'),
        'spend': lambda: tracker._increment_session_spend(1.25),
    }
    assert_serialized(monkeypatch, tracker, 'get_budgets', actions[operation],
                      lambda: tracker.set_budget('session', 20))
    budgets = tracker.get_budgets()
    assert budgets['session'] == 20
    field, expected = {'set': ('daily', 12), 'threshold': ('alert_threshold', 90),
                       'reset': ('monthly', None), 'spend': ('session_spend', 1.25)}[operation]
    assert budgets[field] == expected


@pytest.mark.parametrize('operation', ['add', 'delete', 'import'])
def test_prompt_mutations_are_transactions(data_dir, monkeypatch, operation):
    import json
    pl = _get_module(data_dir)
    pl.save_prompts({'old': {'name': 'old', 'content': 'old'}})
    source = data_dir / 'incoming.json'
    source.write_text(json.dumps({'imported': {'name': 'imported', 'content': 'text'}}), encoding='utf-8')
    def add(name):
        return pl.cmd_add(SimpleNamespace(name=name, text='text', description=None, tag=None))

    actions = {
        'add': lambda: add('first'),
        'delete': lambda: pl.cmd_delete(SimpleNamespace(name='old')),
        'import': lambda: pl.cmd_import(SimpleNamespace(file=str(source), overwrite=False)),
    }
    assert_serialized(monkeypatch, pl, 'load_prompts', actions[operation], lambda: add('second'))
    prompts = pl.load_prompts()
    assert 'second' in prompts
    assert ('old' not in prompts if operation == 'delete'
            else ('first' if operation == 'add' else 'imported') in prompts)
