#!/usr/bin/env python3
"""
gemini_adapter.py — Read Gemini CLI session files from ~/.gemini/
"""

import json
from pathlib import Path


def _gemini_dir() -> Path:
    return Path.home() / ".gemini"


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent Gemini sessions, newest first."""
    root = _gemini_dir()
    if not root.exists():
        return []

    sessions = []
    candidates = (
        list(root.rglob("*.jsonl"))
        + list(root.rglob("*.json"))
    )
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        session = _parse_session_file(path)
        if session:
            sessions.append(session)
        if len(sessions) >= limit:
            break

    return sessions


def _parse_session_file(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    messages = []
    start_time = None
    end_time = None
    total_input = 0
    total_output = 0

    # Try JSONL first
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue

        ts = obj.get("timestamp") or obj.get("createTime")
        if ts:
            if start_time is None:
                start_time = ts
            end_time = ts

        role = obj.get("role", "")
        # Gemini uses "parts" array for content
        parts = obj.get("parts") or []
        content = " ".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if not content:
            content = obj.get("content", "")

        if role and content:
            messages.append({"role": role, "content": str(content)[:200]})

        usage = obj.get("usageMetadata") or {}
        total_input += usage.get("promptTokenCount", 0)
        total_output += usage.get("candidatesTokenCount", 0)

    if not messages:
        return None

    return {
        "provider": "gemini",
        "session_id": path.stem,
        "project": path.parent.name,
        "file": str(path),
        "start_time": start_time or "",
        "end_time": end_time or "",
        "duration": "",
        "turns": len([m for m in messages if m["role"] in ("user", "USER")]),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "messages": messages,
    }


def search_sessions(keyword: str, limit: int = 10) -> list[dict]:
    all_sessions = list_sessions(limit=200)
    kw = keyword.lower()
    results = []
    for s in all_sessions:
        for msg in s.get("messages", []):
            if kw in msg.get("content", "").lower():
                results.append(s)
                break
    return results[:limit]
