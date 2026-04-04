"""MCP server exposing persona and memory system as Claude Code tools."""

from __future__ import annotations

import json
from typing import Any

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
from src.calendar import sync_events_bulk as _sync_cal_events
from src.todos import (
    complete_todo as _complete_todo,
    create_todo as _create_todo,
    delete_todo as _delete_todo,
    get_todo as _get_todo,
    list_todos as _list_todos,
    update_todo as _update_todo,
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
    """Return current traits, active rules, persona name, and top memories. Use at session start."""
    conn = init_db()
    try:
        state = _get_persona_state(conn)
        # Include top ranked memories for session context
        top_memories = _query_memories(conn, limit=10)
        state["memories"] = top_memories
        return state
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
    """Start a reflection cycle: gather signals and return the analysis prompt.

    Returns the prompt for Claude Code to analyze. Pass the JSON response
    to apply_reflection() to apply the changes.
    """
    conn = init_db()
    try:
        reflection_context = run_reflection(conn, trigger_type=trigger_type)
        if reflection_context.get("skipped") or reflection_context.get("reflection_id") is None:
            return {"status": "skipped", "reason": "Threshold not met or no pending signals"}

        return {
            "status": "pending",
            "reflection_id": reflection_context["reflection_id"],
            "prompt": reflection_context["prompt"],
            "signal_count": reflection_context.get("signal_count", 0),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def apply_reflection(reflection_id: int, llm_response: str) -> dict[str, Any]:
    """Apply a reflection result. Takes the JSON analysis from Claude Code and applies changes."""
    conn = init_db()
    try:
        result = complete_reflection(
            conn,
            reflection_id=reflection_id,
            llm_response=llm_response,
        )
        return {"status": "completed", "reflection_id": reflection_id, "summary": result}
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
def get_avatar_reference() -> dict[str, Any]:
    """Get the reference image path used for contextual avatar generation."""
    conn = init_db()
    try:
        row = conn.execute("SELECT reference_path, avatar_path FROM persona_meta WHERE id = 1").fetchone()
        ref = row["reference_path"] if row and row["reference_path"] else (row["avatar_path"] if row else None)
        return {"reference_path": ref}
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


# ── Calendar Sync ──────────────────────────────────────────────


@mcp.tool()
def sync_calendar_events(events_json: str) -> dict[str, Any]:
    """Cache calendar events to local DB for web dashboard display.

    Call this after using gcal_list_events. Pass the raw events JSON array.

    Args:
        events_json: JSON string of events array from gcal_list_events
    """
    conn = init_db()
    try:
        events = json.loads(events_json)
        count = _sync_cal_events(conn, events)
        return {"synced": count}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


# ── Email Sync ─────────────────────────────────────────────────


@mcp.tool()
def sync_emails(emails_json: str) -> dict[str, Any]:
    """Cache Gmail messages to local DB for web dashboard display.

    Call this after using gmail_search_messages. Pass the raw messages JSON array.

    Args:
        emails_json: JSON string of messages array from gmail_search_messages
    """
    conn = init_db()
    try:
        messages = json.loads(emails_json)
        count = 0
        for msg in messages:
            headers = msg.get("headers", {})
            label_ids = msg.get("labelIds", [])

            # Determine category
            category = "personal"
            for lid in label_ids:
                if "PROMOTIONS" in lid:
                    category = "promotions"
                    break
                elif "UPDATES" in lid:
                    category = "updates"
                    break
                elif "SOCIAL" in lid:
                    category = "social"
                    break

            # Parse internal date (epoch ms) to ISO
            internal_ts = msg.get("internalDate", "0")
            from datetime import datetime, timezone
            internal_date = datetime.fromtimestamp(
                int(internal_ts) / 1000, tz=timezone.utc
            ).isoformat()

            conn.execute(
                """INSERT OR REPLACE INTO cached_emails
                   (message_id, thread_id, subject, sender, recipients, cc,
                    snippet, label_ids, category, is_unread, is_important,
                    internal_date, size_estimate, summary, body, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
                (
                    msg.get("messageId"),
                    msg.get("threadId"),
                    headers.get("Subject", "(no subject)"),
                    headers.get("From", ""),
                    headers.get("To", ""),
                    headers.get("Cc", ""),
                    msg.get("snippet", ""),
                    json.dumps(label_ids),
                    category,
                    1 if "UNREAD" in label_ids else 0,
                    1 if "IMPORTANT" in label_ids else 0,
                    internal_date,
                    msg.get("sizeEstimate", 0),
                    msg.get("summary"),
                    msg.get("body"),
                ),
            )
            count += 1
        conn.commit()
        return {"synced": count}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


# ── Todos ─────────────────────────────────────────────────────


@mcp.tool()
def create_todo(
    title: str,
    description: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
    calendar_event_id: str | None = None,
    tags: str | None = None,
) -> dict[str, Any]:
    """Create a new todo item.

    Args:
        title: Short task description
        description: Optional longer details
        priority: low, medium, high, or urgent
        due_date: ISO 8601 date (e.g. '2026-04-03')
        calendar_event_id: Link to a Google Calendar event ID
        tags: Comma-separated tags
    """
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        todo_id = _create_todo(
            conn, title=title, description=description, priority=priority,
            due_date=due_date, calendar_event_id=calendar_event_id, tags=tag_list,
        )
        return {"todo_id": todo_id, "title": title}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def update_todo(
    todo_id: int,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    due_date: str | None = None,
    tags: str | None = None,
) -> dict[str, Any]:
    """Update a todo item.

    Args:
        todo_id: ID of the todo to update
        title: New title (optional)
        description: New description (optional)
        priority: New priority (optional)
        status: pending, in_progress, done, or cancelled (optional)
        due_date: New due date (optional)
        tags: Comma-separated tags to replace existing (optional)
    """
    conn = init_db()
    try:
        tag_list = _parse_tags(tags) if tags is not None else None
        result = _update_todo(conn, todo_id, title=title, description=description,
                              priority=priority, status=status, due_date=due_date, tags=tag_list)
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def complete_todo(todo_id: int) -> dict[str, Any]:
    """Mark a todo as done."""
    conn = init_db()
    try:
        return _complete_todo(conn, todo_id)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def list_todos(
    status: str | None = None,
    priority: str | None = None,
    tags: str | None = None,
    query: str | None = None,
    include_done: bool = False,
    limit: int = 50,
) -> list[dict] | dict:
    """List todo items with optional filters.

    Args:
        status: Filter by status (pending, in_progress, done, cancelled)
        priority: Filter by priority (low, medium, high, urgent)
        tags: Comma-separated tags to filter by
        query: Search in title and description
        include_done: Include done/cancelled items (default false)
        limit: Max items to return
    """
    conn = init_db()
    try:
        tag_list = _parse_tags(tags)
        return _list_todos(conn, status=status, priority=priority, tags=tag_list or None,
                           query=query, include_done=include_done, limit=limit)
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@mcp.tool()
def delete_todo(todo_id: int) -> dict[str, Any]:
    """Delete a todo permanently."""
    conn = init_db()
    try:
        _delete_todo(conn, todo_id)
        return {"status": "deleted", "todo_id": todo_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
