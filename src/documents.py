"""Document management — AI-generated writings with version history."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.db import transaction


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _count_words(text: str) -> int:
    """Count words (handles Korean and mixed text)."""
    return len(text.split())


def _get_tags(conn: sqlite3.Connection, document_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM document_tags WHERE document_id = ? ORDER BY tag",
        (document_id,),
    ).fetchall()
    return [r["tag"] for r in rows]


def _set_tags(conn: sqlite3.Connection, document_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM document_tags WHERE document_id = ?", (document_id,))
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag) VALUES (?, ?)",
            (document_id, tag.strip()),
        )


# ── CRUD ────────────────────────────────────────────────────────


def create_document(
    conn: sqlite3.Connection,
    title: str,
    content: str,
    doc_type: str = "note",
    language: str = "ko",
    tags: list[str] | None = None,
    interaction_id: str | None = None,
) -> int:
    """Create a new document. Returns document id."""
    word_count = _count_words(content)
    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO documents (title, content, doc_type, language, word_count, source_interaction_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, content, doc_type, language, word_count, interaction_id),
        )
        doc_id = cursor.lastrowid

        # Save initial version
        conn.execute(
            """INSERT INTO document_versions (document_id, title, content, version, edited_by, change_summary)
               VALUES (?, ?, ?, 1, 'ai', 'Initial creation')""",
            (doc_id, title, content),
        )

        if tags:
            _set_tags(conn, doc_id, tags)

        return doc_id


def get_document(conn: sqlite3.Connection, document_id: int) -> dict[str, Any] | None:
    """Get a document by id with its tags."""
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if row is None:
        return None
    doc = _row_to_dict(row)
    doc["tags"] = _get_tags(conn, document_id)
    return doc


def update_document(
    conn: sqlite3.Connection,
    document_id: int,
    title: str | None = None,
    content: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    edited_by: str = "ai",
    change_summary: str | None = None,
) -> dict[str, Any]:
    """Update a document. Creates a version snapshot before updating."""
    with transaction(conn):
        current = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if current is None:
            raise ValueError(f"Document {document_id} not found")

        # Get current version number
        ver_row = conn.execute(
            "SELECT MAX(version) as v FROM document_versions WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        new_version = (ver_row["v"] or 0) + 1

        new_title = title if title is not None else current["title"]
        new_content = content if content is not None else current["content"]
        new_status = status if status is not None else current["status"]

        # Save version snapshot
        conn.execute(
            """INSERT INTO document_versions (document_id, title, content, version, edited_by, change_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (document_id, new_title, new_content, new_version, edited_by, change_summary),
        )

        # Update document
        word_count = _count_words(new_content)
        conn.execute(
            """UPDATE documents
               SET title = ?, content = ?, status = ?, word_count = ?,
                   updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (new_title, new_content, new_status, word_count, document_id),
        )

        if tags is not None:
            _set_tags(conn, document_id, tags)

    return get_document(conn, document_id)


def list_documents(
    conn: sqlite3.Connection,
    doc_type: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    query: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """List documents with filters."""
    conditions = []
    params: list[Any] = []

    if doc_type:
        conditions.append("d.doc_type = ?")
        params.append(doc_type)
    if status:
        conditions.append("d.status = ?")
        params.append(status)
    else:
        conditions.append("d.status != 'archived'")
    if query:
        conditions.append("(d.title LIKE ? OR d.content LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

    where = " AND ".join(conditions) if conditions else "1=1"

    if tags:
        # AND logic: must have all tags
        tag_conditions = []
        for tag in tags:
            tag_conditions.append(
                "EXISTS (SELECT 1 FROM document_tags dt WHERE dt.document_id = d.id AND dt.tag = ?)"
            )
            params.append(tag)
        where += " AND " + " AND ".join(tag_conditions)

    params.append(limit)
    rows = conn.execute(
        f"""SELECT d.* FROM documents d
            WHERE {where}
            ORDER BY d.updated_at DESC
            LIMIT ?""",
        params,
    ).fetchall()

    docs = []
    for row in rows:
        doc = _row_to_dict(row)
        doc["tags"] = _get_tags(conn, doc["id"])
        docs.append(doc)
    return docs


def archive_document(conn: sqlite3.Connection, document_id: int) -> None:
    """Archive a document."""
    conn.execute(
        """UPDATE documents SET status = 'archived',
           updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE id = ?""",
        (document_id,),
    )
    conn.commit()


def delete_document(conn: sqlite3.Connection, document_id: int) -> None:
    """Hard delete a document and its versions/tags."""
    with transaction(conn):
        conn.execute("DELETE FROM document_versions WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM document_tags WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def get_document_versions(
    conn: sqlite3.Connection, document_id: int
) -> list[dict[str, Any]]:
    """Get version history for a document."""
    rows = conn.execute(
        """SELECT * FROM document_versions
           WHERE document_id = ? ORDER BY version DESC""",
        (document_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_document_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Get document statistics."""
    total = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]
    by_type = {}
    for row in conn.execute(
        "SELECT doc_type, COUNT(*) as c FROM documents WHERE status != 'archived' GROUP BY doc_type"
    ).fetchall():
        by_type[row["doc_type"]] = row["c"]
    by_status = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) as c FROM documents GROUP BY status"
    ).fetchall():
        by_status[row["status"]] = row["c"]
    total_words = conn.execute(
        "SELECT COALESCE(SUM(word_count), 0) as w FROM documents WHERE status != 'archived'"
    ).fetchone()["w"]
    return {
        "total": total,
        "by_type": by_type,
        "by_status": by_status,
        "total_words": total_words,
    }
