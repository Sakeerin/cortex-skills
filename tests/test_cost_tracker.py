"""Tests for _lib/cost_tracker.py."""

from cost_tracker import CostTracker


def test_load_events_uses_instance_cache(data_dir):
    tracker = CostTracker(data_dir)
    tracker.log_usage("openai", "gpt-4o", 1000, 500)

    first = tracker.load_events()
    second = tracker.load_events()

    assert len(first) == 1
    assert second == first


def test_get_breakdown_aggregates_from_cached_events(data_dir):
    tracker = CostTracker(data_dir)
    tracker.log_usage("openai", "gpt-4o", 1000, 500)
    tracker.log_usage("openai", "gpt-4o", 2000, 1000)

    breakdown = tracker.get_breakdown()

    assert breakdown[("openai", "gpt-4o")]["input_tokens"] == 3000
    assert breakdown[("openai", "gpt-4o")]["output_tokens"] == 1500
    assert breakdown[("openai", "gpt-4o")]["total_tokens"] == 4500


def test_get_budgets_uses_cache_and_updates_after_save(data_dir):
    tracker = CostTracker(data_dir)

    initial = tracker.get_budgets()
    tracker.set_budget("daily", 12.5)
    updated = tracker.get_budgets()

    assert initial["daily"] is None
    assert updated["daily"] == 12.5
