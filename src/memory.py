"""Memory system CRUD — episodic, semantic, and procedural memories."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from src.db import transaction

VALID_MEMORY_TYPES = ("episodic", "semantic", "procedural")
VALID_RELATIONS = ("derived_from", "contradicts", "supports", "supersedes")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _fetch_tags(conn: sqlite3.Connection, memory_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM memory_tags WHERE memory_id = ? ORDER BY tag",
        (memory_id,),
    ).fetchall()
    return [r["tag"] for r in rows]


def _insert_tags(conn: sqlite3.Connection, memory_id: int, tags: list[str]) -> None:
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
            (memory_id, tag),
        )


# ── Memory CRUD ──────────────────────────────────────────────


def add_memory(
    conn: sqlite3.Connection,
    memory_type: str,
    content: str,
    importance: float = 0.5,
    tags: list[str] | None = None,
    interaction_id: str | None = None,
) -> int:
    """Add a new memory or boost an existing duplicate.

    Returns the memory id (new or existing).
    """
    if memory_type not in VALID_MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory_type '{memory_type}'. Must be one of {VALID_MEMORY_TYPES}"
        )

    h = _content_hash(content)

    with transaction(conn):
        existing = conn.execute(
            "SELECT id, importance, confidence FROM memories WHERE content_hash = ?",
            (h,),
        ).fetchone()

        if existing:
            new_importance = min(existing["importance"] + 0.1, 1.0)
            new_confidence = min(existing["confidence"] + 0.1, 1.0)
            conn.execute(
                "UPDATE memories SET importance = ?, confidence = ? WHERE id = ?",
                (new_importance, new_confidence, existing["id"]),
            )
            return existing["id"]

        cur = conn.execute(
            """INSERT INTO memories
               (memory_type, content, content_hash, importance, source_interaction_id)
               VALUES (?, ?, ?, ?, ?)""",
            (memory_type, content, h, importance, interaction_id),
        )
        memory_id = cur.lastrowid

        if tags:
            _insert_tags(conn, memory_id, tags)

    return memory_id


def get_memory(conn: sqlite3.Connection, memory_id: int) -> dict | None:
    """Retrieve a memory by id, incrementing its access count."""
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if row is None:
        return None

    now = _now()
    conn.execute(
        "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
        (now, memory_id),
    )
    conn.commit()

    result = _row_to_dict(row)
    result["access_count"] += 1
    result["last_accessed"] = now
    result["tags"] = _fetch_tags(conn, memory_id)
    return result


def query_memories(
    conn: sqlite3.Connection,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    query: str | None = None,
    limit: int = 20,
    include_archived: bool = False,
) -> list[dict]:
    """Query memories with optional filters.

    Filters by type, tags (AND logic), and content LIKE search.
    Results ordered by importance DESC.
    """
    conditions: list[str] = []
    params: list = []

    if not include_archived:
        conditions.append("m.is_archived = 0")

    if memory_type is not None:
        conditions.append("m.memory_type = ?")
        params.append(memory_type)

    if query is not None:
        conditions.append("m.content LIKE ?")
        params.append(f"%{query}%")

    if tags:
        # AND logic: memory must have ALL specified tags
        conditions.append(
            """m.id IN (
                SELECT memory_id FROM memory_tags
                WHERE tag IN ({placeholders})
                GROUP BY memory_id
                HAVING COUNT(DISTINCT tag) = ?
            )""".format(placeholders=",".join("?" * len(tags)))
        )
        params.extend(tags)
        params.append(len(tags))

    where = " AND ".join(conditions) if conditions else "1=1"
    # Relevance score: importance (50%) + recency (30%) + access frequency (20%)
    sql = f"""
        SELECT m.*,
            (m.importance * 0.5
             + (1.0 / (1.0 + julianday('now') - julianday(m.created_at))) * 0.3
             + MIN(COALESCE(m.access_count, 0) / 10.0, 1.0) * 0.2
            ) AS relevance
        FROM memories m
        WHERE {where}
        ORDER BY relevance DESC
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        d = _row_to_dict(row)
        d["tags"] = _fetch_tags(conn, d["id"])
        d["relevance"] = round(row["relevance"], 3) if "relevance" in row.keys() else None
        # Update access tracking
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (d["id"],),
        )
        results.append(d)
    conn.commit()
    return results


def archive_memory(conn: sqlite3.Connection, memory_id: int) -> None:
    """Soft-delete a memory by setting is_archived = 1."""
    conn.execute("UPDATE memories SET is_archived = 1 WHERE id = ?", (memory_id,))
    conn.commit()


def delete_memory(conn: sqlite3.Connection, memory_id: int) -> None:
    """Hard-delete a memory and its related data (GDPR compliance)."""
    with transaction(conn):
        conn.execute("DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,))
        conn.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
        conn.execute(
            "DELETE FROM memory_links WHERE source_id = ? OR target_id = ?",
            (memory_id, memory_id),
        )
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))


# ── Memory Links ─────────────────────────────────────────────


def link_memories(
    conn: sqlite3.Connection,
    source_id: int,
    target_id: int,
    relation: str,
) -> None:
    """Create a directional link between two memories."""
    if relation not in VALID_RELATIONS:
        raise ValueError(
            f"Invalid relation '{relation}'. Must be one of {VALID_RELATIONS}"
        )
    conn.execute(
        """INSERT OR IGNORE INTO memory_links (source_id, target_id, relation)
           VALUES (?, ?, ?)""",
        (source_id, target_id, relation),
    )
    conn.commit()


def get_linked_memories(
    conn: sqlite3.Connection, memory_id: int
) -> list[dict]:
    """Return all memories linked to the given memory, with relation info."""
    rows = conn.execute(
        """SELECT ml.relation, ml.source_id, ml.target_id, m.*
           FROM memory_links ml
           JOIN memories m ON m.id = CASE
               WHEN ml.source_id = ? THEN ml.target_id
               ELSE ml.source_id
           END
           WHERE ml.source_id = ? OR ml.target_id = ?""",
        (memory_id, memory_id, memory_id),
    ).fetchall()

    results = []
    for row in rows:
        d = _row_to_dict(row)
        d["tags"] = _fetch_tags(conn, d["id"])
        results.append(d)
    return results


# ── Interaction Log ──────────────────────────────────────────


def start_interaction(conn: sqlite3.Connection, interaction_id: str) -> str:
    """Create a new interaction record. Returns the interaction id."""
    conn.execute("INSERT INTO interactions (id) VALUES (?)", (interaction_id,))
    conn.commit()
    return interaction_id


def end_interaction(
    conn: sqlite3.Connection,
    interaction_id: str,
    summary: str | None = None,
    turn_count: int = 0,
    traits_used: dict | None = None,
    rules_applied: list[int] | None = None,
) -> None:
    """Finalize an interaction with summary and metadata."""
    conn.execute(
        """UPDATE interactions
           SET ended_at = ?, summary = ?, turn_count = ?,
               traits_used = ?, rules_applied = ?
           WHERE id = ?""",
        (
            _now(),
            summary,
            turn_count,
            json.dumps(traits_used) if traits_used is not None else None,
            json.dumps(rules_applied) if rules_applied is not None else None,
            interaction_id,
        ),
    )
    conn.commit()


# ── Stats ────────────────────────────────────────────────────


def get_memory_stats(conn: sqlite3.Connection) -> dict:
    """Return aggregate memory statistics."""
    total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) as c FROM memories WHERE is_archived = 0"
    ).fetchone()["c"]
    archived = total - active

    type_rows = conn.execute(
        "SELECT memory_type, COUNT(*) as c FROM memories GROUP BY memory_type"
    ).fetchall()
    by_type = {row["memory_type"]: row["c"] for row in type_rows}

    return {
        "total": total,
        "by_type": by_type,
        "active": active,
        "archived": archived,
    }
