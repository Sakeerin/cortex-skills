#!/usr/bin/env python3
"""
claude_adapter.py — Read Claude Code session files from ~/.claude/projects/
"""

import json
from datetime import datetime
from pathlib import Path


def _claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent Claude sessions, newest first."""
    root = _claude_projects_dir()
    if not root.exists():
        return []

    sessions = []
    # Each project dir contains .jsonl files per session
    for jsonl_file in sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        session = _parse_session_file(jsonl_file)
        if session:
            sessions.append(session)
        if len(sessions) >= limit:
            break

    return sessions


def _parse_session_file(path: Path) -> dict | None:
    """Parse a Claude JSONL session file into a session summary."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    if not lines:
        return None

    messages = []
    session_id = None
    start_time = None
    end_time = None
    total_input = 0
    total_output = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = obj.get("timestamp") or obj.get("ts")
        if ts:
            if start_time is None:
                start_time = ts
            end_time = ts

        role = obj.get("role") or obj.get("type", "")
        content = obj.get("content") or obj.get("message", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )

        if role and content:
            messages.append({"role": role, "content": str(content)[:200]})

        # Token usage
        usage = obj.get("usage") or {}
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)

        if not session_id:
            session_id = obj.get("session_id") or obj.get("id")

    if not messages:
        return None

    # Extract project name from path
    # path is like ~/.claude/projects/<project-encoded>/session.jsonl
    project_parts = path.relative_to(_claude_projects_dir()).parts
    project = project_parts[0] if project_parts else path.parent.name

    # Duration
    duration_str = ""
    if start_time and end_time:
        try:
            t0 = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            secs = int((t1 - t0).total_seconds())
            duration_str = f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
        except (ValueError, TypeError):
            pass

    return {
        "provider": "claude",
        "session_id": session_id or path.stem,
        "project": project,
        "file": str(path),
        "start_time": start_time or "",
        "end_time": end_time or "",
        "duration": duration_str,
        "turns": len([m for m in messages if m["role"] == "user"]),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "messages": messages,
    }


def search_sessions(keyword: str, limit: int = 10) -> list[dict]:
    """Search session content for keyword."""
    all_sessions = list_sessions(limit=200)
    kw = keyword.lower()
    results = []
    for s in all_sessions:
        for msg in s.get("messages", []):
            if kw in msg.get("content", "").lower():
                results.append(s)
                break
    return results[:limit]
