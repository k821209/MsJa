"""MCP server exposing persona and memory system as Claude Code tools."""

from __future__ import annotations

import json
from typing import Any

import anthropic
from mcp.server.fastmcp import FastMCP

from src.db import init_db
from src.memory import (
    add_memory as _add_memory,
    get_memory_stats as _get_memory_stats,
    query_memories as _query_memories,
)
from src.persona import (
    add_rule as _add_rule,
    get_persona_state as _get_persona_state,
    get_trait_history as _get_trait_history,
    override_trait as _override_trait,
)
from src.reflection import (
    complete_reflection,
    run_reflection,
)
from src.signals import record_signal as _record_signal

mcp = FastMCP("persona", description="Private AI Secretary — Persona & Memory System")


def _parse_tags(tags: str | None) -> list[str] | None:
    """Split a comma-separated tag string into a list, or return None."""
    if not tags:
        return None
    return [t.strip() for t in tags.split(",") if t.strip()]


# ── Tools ────────────────────────────────────────────────────


@mcp.tool()
def get_persona_state() -> dict[str, Any]:
    """Return current traits, active rules, and persona name. Use at session start."""
    conn = init_db()
    try:
        return _get_persona_state(conn)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def query_memories(
    memory_type: str | None = None,
    tags: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> list[dict] | dict:
    """Search memories by type, tags (comma-separated), or content query."""
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        return _query_memories(conn, memory_type=memory_type, tags=tag_list, query=query, limit=limit)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def add_memory(
    memory_type: str,
    content: str,
    importance: float = 0.5,
    tags: str | None = None,
) -> dict[str, Any]:
    """Store a new memory. Tags are comma-separated. Returns id and dedup status."""
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        # Check if content already exists by comparing returned id with a fresh query
        existing = conn.execute(
            "SELECT id FROM memories WHERE content_hash = ?",
            (__import__("hashlib").sha256(content.encode("utf-8")).hexdigest(),),
        ).fetchone()

        memory_id = _add_memory(
            conn, memory_type=memory_type, content=content,
            importance=importance, tags=tag_list,
        )
        was_dedup = existing is not None
        return {"memory_id": memory_id, "deduplicated": was_dedup}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def record_signal(
    signal_type: str,
    evidence: str,
    dimension: str | None = None,
    direction: float | None = None,
    magnitude: float = 0.5,
) -> dict[str, Any]:
    """Record an evolution signal (user_feedback, implicit_cue, outcome, correction)."""
    conn = init_db()
    try:
        signal_id = _record_signal(
            conn, signal_type=signal_type, evidence=evidence,
            dimension=dimension, direction=direction, magnitude=magnitude,
        )
        return {"signal_id": signal_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_active_goals() -> list[dict] | dict:
    """Return all active goals."""
    conn = init_db()
    try:
        rows = conn.execute(
            "SELECT * FROM goals WHERE status = 'active' ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def trigger_reflection(trigger_type: str = "manual") -> dict[str, Any]:
    """Start a reflection cycle: gather signals, call LLM for analysis, apply changes."""
    conn = init_db()
    try:
        reflection_context = run_reflection(conn, trigger_type=trigger_type)
        if reflection_context is None:
            return {"status": "skipped", "reason": "No pending signals to reflect on"}

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system="You are a persona reflection engine. Analyze the signals and respond with JSON only.",
            messages=[{"role": "user", "content": json.dumps(reflection_context["prompt"])}],
        )

        analysis_text = response.content[0].text
        result = complete_reflection(
            conn,
            reflection_id=reflection_context["reflection_id"],
            analysis_text=analysis_text,
        )
        return {"status": "completed", "reflection_id": reflection_context["reflection_id"], "summary": result}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_persona_history(trait_key: str, limit: int = 20) -> list[dict] | dict:
    """Return trait evolution timeline for a specific trait."""
    conn = init_db()
    try:
        return _get_trait_history(conn, trait_key=trait_key, limit=limit)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_memory_stats() -> dict[str, Any]:
    """Return memory statistics: total, by type, active, archived."""
    conn = init_db()
    try:
        return _get_memory_stats(conn)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def override_trait(trait_key: str, value: float) -> dict[str, Any]:
    """User override for a trait value. Bypasses max_delta but respects min/max bounds."""
    conn = init_db()
    try:
        _override_trait(conn, trait_key=trait_key, value=value)
        return {"status": "ok", "trait_key": trait_key, "value": value}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def add_rule(
    rule_text: str,
    category: str = "general",
    priority: int = 100,
) -> dict[str, Any]:
    """Add a new user behavioral rule."""
    conn = init_db()
    try:
        rule_id = _add_rule(
            conn, rule_text=rule_text, category=category,
            priority=priority, source="user",
        )
        return {"rule_id": rule_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
