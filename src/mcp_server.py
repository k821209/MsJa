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
    add_image as _add_image,
    add_lore as _add_lore,
    add_rule as _add_rule,
    archive_lore as _archive_lore,
    get_active_images as _get_active_images,
    get_active_lore as _get_active_lore,
    get_lore_history as _get_lore_history,
    get_persona_state as _get_persona_state,
    get_trait_history as _get_trait_history,
    override_trait as _override_trait,
    set_avatar as _set_avatar,
)
from src.documents import (
    archive_document as _archive_document,
    create_document as _create_document,
    get_document as _get_document,
    get_document_stats as _get_document_stats,
    get_document_versions as _get_document_versions,
    list_documents as _list_documents,
    update_document as _update_document,
)
from src.reflection import (
    complete_reflection,
    run_reflection,
)
from src.signals import record_signal as _record_signal

mcp = FastMCP("persona")


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
    """Record an evolution signal.

    Args:
        signal_type: One of 'user_feedback', 'implicit_cue', 'outcome', 'correction'
        evidence: Description of what happened (the observed behavior or feedback)
        dimension: Which trait this relates to (e.g. 'formality', 'verbosity')
        direction: -1.0 (decrease) to +1.0 (increase)
        magnitude: Signal strength 0.0-1.0 (default 0.5)
    """
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
        if reflection_context.get("skipped") or reflection_context.get("reflection_id") is None:
            return {"status": "skipped", "reason": "Threshold not met or no pending signals"}

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system="You are a persona reflection engine. Analyze the signals and respond with JSON only.",
            messages=[{"role": "user", "content": reflection_context["prompt"]}],
        )

        llm_response = response.content[0].text
        result = complete_reflection(
            conn,
            reflection_id=reflection_context["reflection_id"],
            llm_response=llm_response,
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


@mcp.tool()
def add_persona_image(
    image_type: str,
    label: str,
    file_path: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Add a persona image reference.

    Args:
        image_type: One of 'avatar' (main profile), 'expression' (emotion variant), 'scene' (situational)
        label: Name for this image (e.g. 'default', 'happy', 'thinking')
        file_path: Relative path from project root (e.g. 'persona/avatar/default.png')
        description: What this image represents
    """
    conn = init_db()
    try:
        image_id = _add_image(
            conn, image_type=image_type, label=label,
            file_path=file_path, description=description,
        )
        return {"image_id": image_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_persona_images(image_type: str | None = None) -> list[dict] | dict:
    """Get active persona images. Optionally filter by type: avatar, expression, scene."""
    conn = init_db()
    try:
        return _get_active_images(conn, image_type=image_type)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def set_persona_avatar(file_path: str) -> dict[str, Any]:
    """Set the main avatar image path.

    Args:
        file_path: Relative path from project root (e.g. 'persona/avatar/minji.png')
    """
    conn = init_db()
    try:
        _set_avatar(conn, file_path=file_path)
        return {"status": "ok", "avatar_path": file_path}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_lore(category: str | None = None, limit: int = 20) -> list[dict] | dict:
    """Get active lore entries (self-narrative). Optionally filter by category: identity, philosophy, behavior, aesthetic."""
    conn = init_db()
    try:
        return _get_active_lore(conn, category=category, limit=limit)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def add_lore_entry(
    content: str,
    significance: float = 0.5,
    category: str = "identity",
) -> dict[str, Any]:
    """Add a new lore entry to the persona's self-narrative.

    Args:
        content: The lore statement describing an aspect of the persona's identity
        significance: How central to identity (0.0-1.0)
        category: One of 'identity', 'philosophy', 'behavior', 'aesthetic', 'voice'
    """
    conn = init_db()
    try:
        lore_id = _add_lore(
            conn, content=content, significance=significance,
            category=category, source="user",
        )
        return {"lore_id": lore_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def archive_lore_entry(lore_id: int) -> dict[str, Any]:
    """Archive a lore entry (soft delete). The lore is no longer active but preserved in history."""
    conn = init_db()
    try:
        _archive_lore(conn, lore_id=lore_id, changed_by="user")
        return {"status": "archived", "lore_id": lore_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def trace_lore_evolution(lore_id: int) -> list[dict] | dict:
    """Trace the evolution chain of a lore entry back to its origin."""
    conn = init_db()
    try:
        return _get_lore_history(conn, lore_id=lore_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


# ── Documents ──────────────────────────────────────────────────


@mcp.tool()
def write_document(
    title: str,
    content: str,
    doc_type: str = "note",
    language: str = "ko",
    tags: str | None = None,
) -> dict[str, Any]:
    """Write and save a document. Content should be markdown.

    Args:
        title: Document title
        content: Document body (markdown)
        doc_type: One of 'note', 'draft', 'summary', 'report', 'letter', 'creative', 'plan', 'log'
        language: Language code (default: 'ko')
        tags: Comma-separated tags
    """
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        doc_id = _create_document(
            conn, title=title, content=content, doc_type=doc_type,
            language=language, tags=tag_list,
        )
        return {"document_id": doc_id, "title": title, "doc_type": doc_type}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def read_document(document_id: int) -> dict[str, Any]:
    """Read a saved document by its ID."""
    conn = init_db()
    try:
        doc = _get_document(conn, document_id)
        if doc is None:
            return {"error": f"Document {document_id} not found"}
        return doc
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def edit_document(
    document_id: int,
    title: str | None = None,
    content: str | None = None,
    status: str | None = None,
    tags: str | None = None,
    change_summary: str | None = None,
) -> dict[str, Any]:
    """Edit an existing document. Creates a version snapshot before updating.

    Args:
        document_id: ID of the document to edit
        title: New title (optional)
        content: New content as markdown (optional)
        status: New status: 'draft', 'final', 'archived' (optional)
        tags: Comma-separated tags to replace existing tags (optional)
        change_summary: Description of what changed (optional)
    """
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        doc = _update_document(
            conn, document_id=document_id, title=title, content=content,
            status=status, tags=tag_list, edited_by="ai", change_summary=change_summary,
        )
        return doc
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def search_documents(
    doc_type: str | None = None,
    status: str | None = None,
    tags: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> list[dict] | dict:
    """Search saved documents by type, status, tags, or content.

    Args:
        doc_type: Filter by type (note, draft, summary, report, letter, creative, plan, log)
        status: Filter by status (draft, final, archived)
        tags: Comma-separated tags (AND logic)
        query: Search in title and content
        limit: Max results (default 20)
    """
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        return _list_documents(
            conn, doc_type=doc_type, status=status,
            tags=tag_list, query=query, limit=limit,
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_document_history(document_id: int) -> list[dict] | dict:
    """Get version history for a document."""
    conn = init_db()
    try:
        return _get_document_versions(conn, document_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
