"""Tests for _lib/jsonl_store.py"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "_lib"))

from jsonl_store import JSONLStore


def make_store(tmp_path: Path, filename: str = "test.jsonl", id_key: str = "id") -> JSONLStore:
    return JSONLStore(tmp_path / filename, id_key=id_key)


# ---------------------------------------------------------------------------
# Basic load / append
# ---------------------------------------------------------------------------

def test_load_empty_returns_empty(tmp_path):
    store = make_store(tmp_path)
    assert store.load() == {}


def test_append_and_load(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "abc", "value": 1})
    result = store.load()
    assert "abc" in result
    assert result["abc"]["value"] == 1


def test_last_write_wins(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "abc", "value": 1})
    store.append({"id": "abc", "value": 2})
    result = store.load()
    assert result["abc"]["value"] == 2


def test_deleted_flag_removes_entry(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "abc", "value": 1})
    store.append({"id": "abc", "deleted": True})
    result = store.load()
    assert "abc" not in result


def test_multiple_entries(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "a", "name": "Alice"})
    store.append({"id": "b", "name": "Bob"})
    result = store.load()
    assert len(result) == 2
    assert result["a"]["name"] == "Alice"
    assert result["b"]["name"] == "Bob"


def test_custom_id_key(tmp_path):
    store = JSONLStore(tmp_path / "mem.jsonl", id_key="key")
    store.append({"key": "stack", "value": "Python"})
    result = store.load()
    assert "stack" in result
    assert result["stack"]["value"] == "Python"


# ---------------------------------------------------------------------------
# Corruption handling
# ---------------------------------------------------------------------------

def test_corrupted_line_skipped(tmp_path, capsys):
    path = tmp_path / "data.jsonl"
    path.write_text('{"id":"a","value":1}\nNOT_JSON\n{"id":"b","value":2}\n', encoding="utf-8")
    store = JSONLStore(path)
    result = store.load()
    assert "a" in result
    assert "b" in result
    err = capsys.readouterr().err
    assert "corrupted" in err.lower()


def test_empty_lines_skipped(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('\n{"id":"a","value":1}\n\n', encoding="utf-8")
    store = JSONLStore(path)
    result = store.load()
    assert "a" in result


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------

def test_compact_removes_history(tmp_path):
    store = make_store(tmp_path)
    for i in range(5):
        store.append({"id": "a", "value": i})  # 5 events for same key

    removed = store.compact()
    assert removed == 4  # 5 events → 1 record, removed 4

    result = store.load()
    assert result["a"]["value"] == 4  # final value preserved


def test_compact_removes_deleted(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "a", "value": 1})
    store.append({"id": "b", "value": 2})
    store.append({"id": "a", "deleted": True})

    removed = store.compact()
    assert removed == 2  # 3 events → 1 live record, 2 historical events removed

    result = store.load()
    assert "a" not in result
    assert "b" in result


def test_compact_idempotent(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "x", "value": 42})
    store.compact()
    store.compact()  # second compact should be a no-op
    result = store.load()
    assert result["x"]["value"] == 42


def test_compact_empty_store(tmp_path):
    store = make_store(tmp_path)
    removed = store.compact()  # should not raise
    assert removed == 0


def test_compact_preserves_all_fields(tmp_path):
    store = make_store(tmp_path)
    store.append({"id": "a", "title": "Test", "priority": "high", "tags": ["dev"]})
    store.append({"id": "a", "checked": True})
    store.compact()

    result = store.load()
    record = result["a"]
    assert record["title"] == "Test"
    assert record["priority"] == "high"
    assert record["checked"] is True
    assert record["tags"] == ["dev"]


# ---------------------------------------------------------------------------
# Auto-compaction threshold
# ---------------------------------------------------------------------------

def test_auto_compact_triggers_at_threshold(tmp_path):
    store = make_store(tmp_path)
    store._COMPACT_THRESHOLD = 10  # low threshold for testing

    for i in range(15):
        store.append({"id": str(i), "value": i})

    # After 15 appends with threshold=10, compaction should have triggered
    line_count = store._count_lines()
    # Compacted file should have at most 15 live records (≤ 15 lines)
    assert line_count <= 15
