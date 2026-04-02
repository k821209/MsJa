"""Todo management — task tracking for the AI secretary."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from src.db import transaction


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _get_tags(conn: sqlite3.Connection, todo_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM todo_tags WHERE todo_id = ? ORDER BY tag",
        (todo_id,),
    ).fetchall()
    return [r["tag"] for r in rows]


def _set_tags(conn: sqlite3.Connection, todo_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM todo_tags WHERE todo_id = ?", (todo_id,))
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO todo_tags (todo_id, tag) VALUES (?, ?)",
            (todo_id, tag.strip()),
        )


def _enrich(conn: sqlite3.Connection, todo: dict[str, Any]) -> dict[str, Any]:
    """Add tags and is_overdue flag."""
    todo["tags"] = _get_tags(conn, todo["id"])
    todo["is_overdue"] = (
        todo["due_date"] is not None
        and todo["status"] in ("pending", "in_progress")
        and todo["due_date"][:10] < date.today().isoformat()
    )
    return todo


# ── CRUD ────────────────────────────────────────────────────────


def create_todo(
    conn: sqlite3.Connection,
    title: str,
    description: str | None = None,
    priority: str = "medium",
    due_date: str | None = None,
    calendar_event_id: str | None = None,
    tags: list[str] | None = None,
) -> int:
    """Create a new todo. Returns todo id."""
    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO todos (title, description, priority, due_date, calendar_event_id)
               VALUES (?, ?, ?, ?, ?)""",
            (title, description, priority, due_date, calendar_event_id),
        )
        todo_id = cursor.lastrowid
        if tags:
            _set_tags(conn, todo_id, tags)
        return todo_id


def get_todo(conn: sqlite3.Connection, todo_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        return None
    return _enrich(conn, _row_to_dict(row))


def update_todo(
    conn: sqlite3.Connection,
    todo_id: int,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    due_date: str | None = ...,
    calendar_event_id: str | None = ...,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Update a todo. Returns updated todo."""
    with transaction(conn):
        current = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        if current is None:
            raise ValueError(f"Todo {todo_id} not found")

        sets = ["updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"]
        params: list[Any] = []

        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if priority is not None:
            sets.append("priority = ?")
            params.append(priority)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
            if status == "done" and current["status"] != "done":
                sets.append("completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')")
            elif status != "done":
                sets.append("completed_at = NULL")
        if due_date is not ...:
            sets.append("due_date = ?")
            params.append(due_date)
        if calendar_event_id is not ...:
            sets.append("calendar_event_id = ?")
            params.append(calendar_event_id)

        params.append(todo_id)
        conn.execute(f"UPDATE todos SET {', '.join(sets)} WHERE id = ?", params)

        if tags is not None:
            _set_tags(conn, todo_id, tags)

    return get_todo(conn, todo_id)


def complete_todo(conn: sqlite3.Connection, todo_id: int) -> dict[str, Any]:
    """Mark a todo as done."""
    return update_todo(conn, todo_id, status="done")


def delete_todo(conn: sqlite3.Connection, todo_id: int) -> None:
    with transaction(conn):
        conn.execute("DELETE FROM todo_tags WHERE todo_id = ?", (todo_id,))
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))


def list_todos(
    conn: sqlite3.Connection,
    status: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    query: str | None = None,
    include_done: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if status:
        conditions.append("t.status = ?")
        params.append(status)
    elif not include_done:
        conditions.append("t.status NOT IN ('done', 'cancelled')")

    if priority:
        conditions.append("t.priority = ?")
        params.append(priority)
    if query:
        conditions.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if tags:
        for tag in tags:
            conditions.append(
                "EXISTS (SELECT 1 FROM todo_tags tt WHERE tt.todo_id = t.id AND tt.tag = ?)"
            )
            params.append(tag)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    rows = conn.execute(
        f"""SELECT t.* FROM todos t
            WHERE {where}
            ORDER BY
              CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
              t.due_date IS NULL, t.due_date,
              t.created_at DESC
            LIMIT ?""",
        params,
    ).fetchall()

    return [_enrich(conn, _row_to_dict(r)) for r in rows]


def get_todo_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) as c FROM todos").fetchone()["c"]
    by_status = {}
    for row in conn.execute("SELECT status, COUNT(*) as c FROM todos GROUP BY status").fetchall():
        by_status[row["status"]] = row["c"]
    by_priority = {}
    for row in conn.execute(
        "SELECT priority, COUNT(*) as c FROM todos WHERE status NOT IN ('done','cancelled') GROUP BY priority"
    ).fetchall():
        by_priority[row["priority"]] = row["c"]
    overdue = conn.execute(
        "SELECT COUNT(*) as c FROM todos WHERE status IN ('pending','in_progress') AND due_date < date('now')"
    ).fetchone()["c"]
    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "overdue": overdue,
    }
