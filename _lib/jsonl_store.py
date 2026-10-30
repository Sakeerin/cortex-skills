#!/usr/bin/env python3
"""
jsonl_store.py — Shared event-sourced JSONL storage for AI Skills

Provides a JSONLStore class used by todo, notes, memory, and other skills
that use append-only JSONL event logs.

Usage:
  from jsonl_store import JSONLStore

  store = JSONLStore(path, id_key="id")
  state = store.load()        # dict[id -> record]
  store.append(event)         # append + auto-compact when needed
  removed = store.compact()   # rewrite to final state only
"""

import json
import sys
from pathlib import Path

from file_lock import atomic_write, data_lock


class JSONLStore:
    """
    Append-only JSONL event log with automatic compaction.

    Each line in the file is a JSON object with a unique key (id_key).
    Later events for the same key are merged (last-write-wins).
    Events with `"deleted": true` remove the entry from the live state.

    Compaction rewrites the file to only current live records, eliminating
    historical events and keeping the file size bounded.
    """

    # Auto-compact when total lines exceed live records by this multiplier.
    # e.g. 3x: compact when 300 lines represent only 100 live records.
    _COMPACT_RATIO = 3
    # Also auto-compact when total line count exceeds this absolute limit.
    _COMPACT_THRESHOLD = 500

    def __init__(self, path: Path, id_key: str = "id"):
        """
        Args:
            path:   Path to the .jsonl file.
            id_key: Field used as the unique record identifier (default "id").
        """
        self.path = path
        self.id_key = id_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """
        Reconstruct current live state from the JSONL event log.

        Returns:
            dict mapping id_key → merged record dict (last-write-wins).
            Events with ``deleted=True`` are excluded from the result.
        """
        if not self.path.exists():
            return {}

        result = {}
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        f"Warning: skipping corrupted line in {self.path.name}",
                        file=sys.stderr,
                    )
                    continue
                id_val = obj.get(self.id_key)
                if not id_val:
                    continue
                if obj.get("deleted"):
                    result.pop(id_val, None)
                else:
                    result[id_val] = {**result.get(id_val, {}), **obj}

        return result

    def append(self, event: dict) -> None:
        """
        Append a single event to the JSONL file.

        Creates the parent directory if it does not exist.
        Triggers auto-compaction if the file has grown too large.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with data_lock(self.path.parent):
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._maybe_compact()

    def compact(self) -> int:
        """
        Rewrite the JSONL file to contain only current live records.

        Eliminates historical events (edits, deletes) and deleted entries.
        Uses a temp file + atomic rename to avoid data loss on interrupt.

        Returns:
            Number of lines removed by compaction.
        """
        if not self.path.exists():
            return 0

        with data_lock(self.path.parent):
            state = self.load()
            old_count = self._count_lines()
            content = ''.join(json.dumps(record, ensure_ascii=False) + '\n'
                              for record in state.values())
            atomic_write(self.path, content.encode('utf-8'))
            return old_count - len(state)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_lines(self) -> int:
        """Count non-empty lines in the JSONL file (fast binary scan)."""
        if not self.path.exists():
            return 0
        count = 0
        with open(self.path, "rb") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def _maybe_compact(self) -> None:
        """Trigger compaction if the file has grown too large."""
        total = self._count_lines()
        if total < self._COMPACT_THRESHOLD:
            return
        if total >= max(len(self.load()), 1) * self._COMPACT_RATIO:
            self.compact()
