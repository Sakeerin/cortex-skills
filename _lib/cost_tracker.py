#!/usr/bin/env python3
"""
cost_tracker.py - Shared JSONL-based usage and budget tracking.
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ai_provider import get_data_dir

DEFAULT_RATES = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gpt-5": {"input": 1.25, "output": 10.0},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "mistral-large": {"input": 2.0, "output": 6.0},
    "mistral-small": {"input": 0.2, "output": 0.6},
}

FREE_PROVIDER_PREFIXES = ("ollama", "lmstudio", "llama", "codellama", "phi")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


class CostTracker:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.data_dir / "cost-log.jsonl"
        self.budget_path = self.data_dir / "budget.json"
        self.rate_path = Path(__file__).resolve().parent.parent / "cost-rates.json"

    def load_rates(self) -> dict[str, dict[str, float]]:
        rates = dict(DEFAULT_RATES)
        if self.rate_path.exists():
            try:
                payload = json.loads(self.rate_path.read_text(encoding="utf-8"))
                for model, model_rates in payload.items():
                    if isinstance(model_rates, dict):
                        rates[model.lower()] = {
                            "input": float(model_rates.get("input", 0.0)),
                            "output": float(model_rates.get("output", 0.0)),
                        }
            except (json.JSONDecodeError, ValueError):
                pass
        return rates

    def get_rate(self, model: str, provider: str | None = None) -> dict[str, float]:
        model_key = (model or "").lower()
        provider_key = (provider or "").lower()
        if provider_key in {"ollama", "lmstudio"}:
            return {"input": 0.0, "output": 0.0}
        if any(model_key.startswith(prefix) for prefix in FREE_PROVIDER_PREFIXES):
            return {"input": 0.0, "output": 0.0}
        rates = self.load_rates()
        if model_key in rates:
            return rates[model_key]
        for known, value in rates.items():
            if model_key.startswith(known):
                return value
        return {"input": 0.0, "output": 0.0}

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        rate = self.get_rate(model, provider)
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
        cost_usd = self.estimate_cost(provider, model, input_tokens, output_tokens)
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp or now_iso(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost_usd,
            "session_id": session_id or "default",
            "metadata": metadata or {},
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._increment_session_spend(cost_usd)
        return event

    def load_events(self) -> list[dict[str, object]]:
        if not self.log_path.exists():
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
        return events

    def get_daily_cost(self, target_date: date | None = None) -> float:
        target_date = target_date or datetime.now().astimezone().date()
        return round(sum(event["cost_usd"] for event in self._events_for_day(target_date)), 6)

    def get_weekly_cost(self, target_date: date | None = None) -> float:
        target_date = target_date or datetime.now().astimezone().date()
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        return round(
            sum(
                event["cost_usd"]
                for event in self.load_events()
                if week_start <= self._event_date(event) <= week_end
            ),
            6,
        )

    def get_monthly_cost(self, target_date: date | None = None) -> float:
        target_date = target_date or datetime.now().astimezone().date()
        return round(
            sum(
                event["cost_usd"]
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
                {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
            )
            bucket["input_tokens"] += int(event.get("input_tokens", 0))
            bucket["output_tokens"] += int(event.get("output_tokens", 0))
            bucket["total_tokens"] += int(event.get("total_tokens", 0))
            bucket["cost_usd"] += float(event.get("cost_usd", 0.0))
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
        if not self.budget_path.exists():
            return {
                "daily": None,
                "session": None,
                "monthly": None,
                "alert_threshold": 80,
                "session_spend": 0.0,
            }
        try:
            data = json.loads(self.budget_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        return {
            "daily": data.get("daily"),
            "session": data.get("session"),
            "monthly": data.get("monthly"),
            "alert_threshold": data.get("alert_threshold", 80),
            "session_spend": float(data.get("session_spend", 0.0)),
        }

    def save_budgets(self, budgets: dict[str, object]) -> None:
        self.budget_path.write_text(json.dumps(budgets, indent=2), encoding="utf-8")

    def set_budget(self, budget_type: str, amount: float) -> dict[str, object]:
        budgets = self.get_budgets()
        budgets[budget_type] = round(float(amount), 2)
        self.save_budgets(budgets)
        return budgets

    def set_alert_threshold(self, threshold: int) -> dict[str, object]:
        budgets = self.get_budgets()
        budgets["alert_threshold"] = int(threshold)
        self.save_budgets(budgets)
        return budgets

    def reset_budget(self, budget_type: str) -> dict[str, object]:
        budgets = self.get_budgets()
        if budget_type == "session":
            budgets["session_spend"] = 0.0
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
            used = float(budgets.get("session_spend", 0.0))
        else:
            raise ValueError(f"Unsupported budget type: {budget_type}")
        exceeded = limit is not None and used > float(limit)
        return round(used, 6), (float(limit) if limit is not None else None), exceeded

    def _increment_session_spend(self, amount: float) -> None:
        budgets = self.get_budgets()
        budgets["session_spend"] = round(float(budgets.get("session_spend", 0.0)) + amount, 6)
        self.save_budgets(budgets)

    def _events_for_day(self, target_date: date) -> list[dict[str, object]]:
        return [event for event in self.load_events() if self._event_date(event) == target_date]

    @staticmethod
    def _event_date(event: dict[str, object]) -> date:
        raw = str(event.get("timestamp", ""))
        try:
            return datetime.fromisoformat(raw).astimezone().date()
        except ValueError:
            return datetime.now().astimezone().date()
