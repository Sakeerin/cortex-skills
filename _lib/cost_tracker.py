#!/usr/bin/env python3
"""
cost_tracker.py - Shared JSONL-based usage and budget tracking.
"""

from __future__ import annotations

import csv
import json
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ai_provider import get_data_dir
from file_lock import atomic_write, data_lock
from data_scope import current_scope
from errors import DataError
from data_manager import validate_document

from model_registry import get_registry


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


class CostTracker:
    def __init__(self, data_dir: Path | None = None):
        self.scope = current_scope()
        self.data_dir = data_dir or get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.data_dir / "cost-log.jsonl"
        self.budget_path = self.data_dir / "budget.json"
        self.rate_path = Path(__file__).resolve().parent.parent / "cost-rates.json"
        self._registry = get_registry(rate_path=self.rate_path)
        self._events_cache: list[dict[str, object]] | None = None
        self._events_signature: tuple | None = None
        self._budgets_cache: dict[str, object] | None = None
        self._budgets_signature: tuple | None = None

    def load_rates(self) -> dict[str, dict[str, float]]:
        return self.registry.rate_table()

    @property
    def registry(self):
        # Keep one configuration snapshot per tracker, while preserving the
        # legacy rate_path override used by integrations and isolated tests.
        if self._registry.rate_path != self.rate_path:
            self._registry = get_registry(rate_path=self.rate_path)
        return self._registry

    def pricing_signature(self):
        return self.registry.signature()

    def get_rate(self, model: str, provider: str | None = None) -> dict[str, float]:
        return self.registry.rate(model, provider) or {'input': 0.0, 'output': 0.0}

    def has_rate(self, model: str, provider: str) -> bool:
        return self.registry.rate(model, provider) is not None

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        return self.price_usage(provider, model, input_tokens, output_tokens) or 0.0

    def price_usage(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float | None:
        """Resolve availability and prices from the same registry snapshot."""
        rate = self.registry.rate(model, provider)
        if rate is None:
            return None
        return round(
            (input_tokens * rate["input"] / 1_000_000)
            + (output_tokens * rate["output"] / 1_000_000),
            6,
        )

    def log_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        *,
        session_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, object]:
        input_tokens = int(input_tokens)
        output_tokens = int(output_tokens)
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError('Token counts must be nonnegative')
        scope = self.scope
        if scope.kind == 'session':
            if session_id is not None and session_id != scope.session:
                raise ValueError('--session-id must match the selected session scope')
            session_id = scope.session
        cost_usd = self.price_usage(provider, model, input_tokens, output_tokens)
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp or now_iso(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost_usd,
            "pricing_status": 'estimated' if cost_usd is not None else 'unknown',
            "session_id": session_id or "default",
            "metadata": metadata or {},
        }
        with data_lock(self.data_dir):
            # Validate budget data before appending, so a corrupt budget cannot
            # turn a rejected command into an unreported usage write.
            self.get_budgets()
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            self.invalidate_events()
            if cost_usd is not None:
                self._increment_session_spend(cost_usd)
        return event

    def invalidate_events(self) -> None:
        self._events_cache = None
        self._events_signature = None

    @staticmethod
    def event_cost(event: dict) -> float:
        value = event.get('cost_usd')
        return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else 0.0

    def load_events(self) -> list[dict[str, object]]:
        signature = self._file_signature(self.log_path)
        if self._events_cache is not None and self._events_signature == signature:
            return list(self._events_cache)

        if not self.log_path.exists():
            self._events_cache = []
            self._events_signature = signature
            return []

        events: list[dict[str, object]] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        self._events_cache = list(events)
        self._events_signature = signature
        return list(events)

    def get_daily_cost(self, target_date: date | None = None) -> float:
        target_date = target_date or datetime.now().astimezone().date()
        return round(sum(self.event_cost(event) for event in self._events_for_day(target_date)), 6)

    def get_weekly_cost(self, target_date: date | None = None) -> float:
        target_date = target_date or datetime.now().astimezone().date()
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        return round(
            sum(
                self.event_cost(event)
                for event in self.load_events()
                if week_start <= self._event_date(event) <= week_end
            ),
            6,
        )

    def get_monthly_cost(self, target_date: date | None = None) -> float:
        target_date = target_date or datetime.now().astimezone().date()
        return round(
            sum(
                self.event_cost(event)
                for event in self.load_events()
                if self._event_date(event).year == target_date.year
                and self._event_date(event).month == target_date.month
            ),
            6,
        )

    def get_breakdown(self) -> dict[tuple[str, str], dict[str, float]]:
        breakdown: dict[tuple[str, str], dict[str, float]] = {}
        for event in self.load_events():
            key = (event.get("provider", "unknown"), event.get("model", "unknown"))
            bucket = breakdown.setdefault(
                key,
                {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                 "cost_usd": 0.0, "unpriced_events": 0},
            )
            bucket["input_tokens"] += int(event.get("input_tokens", 0))
            bucket["output_tokens"] += int(event.get("output_tokens", 0))
            bucket["total_tokens"] += int(event.get("total_tokens", 0))
            bucket["cost_usd"] += self.event_cost(event)
            bucket["unpriced_events"] += event.get('cost_usd') is None
        for bucket in breakdown.values():
            bucket["cost_usd"] = round(bucket["cost_usd"], 6)
        return breakdown

    def export_csv(self, output_path: Path) -> Path:
        events = self.load_events()
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp",
                    "provider",
                    "model",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "cost_usd",
                    "session_id",
                ],
            )
            writer.writeheader()
            for event in events:
                writer.writerow({key: event.get(key) for key in writer.fieldnames})
        return output_path

    def get_budgets(self) -> dict[str, object]:
        signature = self._file_signature(self.budget_path)
        if self._budgets_cache is not None and self._budgets_signature == signature:
            return dict(self._budgets_cache)

        if not self.budget_path.exists():
            budgets = {
                "daily": None,
                "session": None,
                "monthly": None,
                "alert_threshold": 80,
                "session_spend": 0.0,
            }
        else:
            data = json.loads(self.budget_path.read_text(encoding="utf-8"))
            error = validate_document('budget.json', data)
            if error:
                raise DataError(f'Invalid budget data: {error}; run ai-data doctor')
            budgets = {
                "daily": data.get("daily"),
                "session": data.get("session"),
                "monthly": data.get("monthly"),
                "alert_threshold": data.get("alert_threshold", 80),
                "session_spend": float(data.get("session_spend", 0.0)),
                "session_baseline": float(data.get('session_baseline', 0.0)),
            }

        self._budgets_cache = dict(budgets)
        self._budgets_signature = signature
        return dict(budgets)

    def save_budgets(self, budgets: dict[str, object]) -> None:
        with data_lock(self.data_dir):
            atomic_write(self.budget_path, json.dumps(budgets, indent=2).encode('utf-8'))
            self._budgets_cache = dict(budgets)
            self._budgets_signature = self._file_signature(self.budget_path)

    def set_budget(self, budget_type: str, amount: float) -> dict[str, object]:
        if budget_type not in {'daily', 'session', 'monthly'}:
            raise ValueError(f'Unsupported budget type: {budget_type}')
        if not math.isfinite(float(amount)) or amount < 0:
            raise ValueError('Budget must be a finite, nonnegative amount')
        with data_lock(self.data_dir):
            budgets = self.get_budgets()
            budgets[budget_type] = round(float(amount), 2)
            self.save_budgets(budgets)
        return budgets

    def set_alert_threshold(self, threshold: int) -> dict[str, object]:
        if not 0 <= threshold <= 100:
            raise ValueError('Alert threshold must be between 0 and 100')
        with data_lock(self.data_dir):
            budgets = self.get_budgets()
            budgets["alert_threshold"] = int(threshold)
            self.save_budgets(budgets)
        return budgets

    def reset_budget(self, budget_type: str) -> dict[str, object]:
        if budget_type not in {'daily', 'session', 'monthly'}:
            raise ValueError(f'Unsupported budget type: {budget_type}')
        with data_lock(self.data_dir):
            budgets = self.get_budgets()
            if budget_type == "session":
                budgets["session_spend"] = 0.0
                if self.scope.kind == 'session':
                    budgets['session_baseline'] = self._session_total()
            else:
                budgets[budget_type] = None
            self.save_budgets(budgets)
        return budgets

    def check_budget(self, budget_type: str) -> tuple[float, float | None, bool]:
        budgets = self.get_budgets()
        limit = budgets.get(budget_type)
        if budget_type == "daily":
            used = self.get_daily_cost()
        elif budget_type == "monthly":
            used = self.get_monthly_cost()
        elif budget_type == "session":
            used = (max(self._session_total() - float(budgets.get('session_baseline', 0.0)), 0.0)
                    if self.scope.kind == 'session' else float(budgets.get('session_spend', 0.0)))
        else:
            raise ValueError(f"Unsupported budget type: {budget_type}")
        exceeded = limit is not None and used > float(limit)
        return round(used, 6), (float(limit) if limit is not None else None), exceeded

    def _increment_session_spend(self, amount: float) -> None:
        with data_lock(self.data_dir):
            budgets = self.get_budgets()
            budgets["session_spend"] = round(float(budgets.get("session_spend", 0.0)) + amount, 6)
            self.save_budgets(budgets)

    def _session_total(self) -> float:
        return sum(self.event_cost(event) for event in self.load_events()
                   if event.get('session_id') == self.scope.session)

    def _events_for_day(self, target_date: date) -> list[dict[str, object]]:
        return [event for event in self.load_events() if self._event_date(event) == target_date]

    @staticmethod
    def _event_date(event: dict[str, object]) -> date:
        raw = str(event.get("timestamp", ""))
        try:
            return datetime.fromisoformat(raw).astimezone().date()
        except ValueError:
            return datetime.now().astimezone().date()

    @staticmethod
    def _file_signature(path: Path) -> tuple:
        if not path.exists():
            return (str(path), None, None)
        stat = path.stat()
        return (str(path), stat.st_mtime_ns, stat.st_size)
