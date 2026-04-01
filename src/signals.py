"""Evolution signal collection — collect and query signals that drive persona evolution."""

from __future__ import annotations

import sqlite3
from typing import Any

from src.db import transaction

VALID_SIGNAL_TYPES = frozenset({"user_feedback", "implicit_cue", "outcome", "correction"})


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def record_signal(
    conn: sqlite3.Connection,
    signal_type: str,
    evidence: str,
    dimension: str | None = None,
    direction: float | None = None,
    magnitude: float = 0.5,
    interaction_id: str | None = None,
) -> int:
    """Record an evolution signal. Returns the signal id.

    Validates signal_type is one of: user_feedback, implicit_cue, outcome, correction.
    """
    if signal_type not in VALID_SIGNAL_TYPES:
        raise ValueError(
            f"Invalid signal_type '{signal_type}'. Must be one of: {', '.join(sorted(VALID_SIGNAL_TYPES))}"
        )

    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO evolution_signals
               (signal_type, evidence, dimension, direction, magnitude, interaction_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (signal_type, evidence, dimension, direction, magnitude, interaction_id),
        )
    return cursor.lastrowid


def get_unconsumed_signals(
    conn: sqlite3.Connection, limit: int = 100
) -> list[dict[str, Any]]:
    """Return signals not yet consumed by a reflection, ordered by creation time."""
    rows = conn.execute(
        """SELECT * FROM evolution_signals
           WHERE consumed_by IS NULL
           ORDER BY created_at
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_signal_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return summary of unconsumed signals.

    Returns:
        {"count": N, "total_magnitude": X, "by_dimension": {dim: {"count": n, "total_magnitude": m}}}
    """
    row = conn.execute(
        """SELECT COUNT(*) AS count, COALESCE(SUM(magnitude), 0.0) AS total_magnitude
           FROM evolution_signals WHERE consumed_by IS NULL"""
    ).fetchone()

    by_dimension: dict[str, dict[str, Any]] = {}
    dim_rows = conn.execute(
        """SELECT dimension, COUNT(*) AS count, SUM(magnitude) AS total_magnitude
           FROM evolution_signals
           WHERE consumed_by IS NULL AND dimension IS NOT NULL
           GROUP BY dimension"""
    ).fetchall()
    for dr in dim_rows:
        by_dimension[dr["dimension"]] = {
            "count": dr["count"],
            "total_magnitude": dr["total_magnitude"],
        }

    return {
        "count": row["count"],
        "total_magnitude": row["total_magnitude"],
        "by_dimension": by_dimension,
    }


def consume_signals(
    conn: sqlite3.Connection, signal_ids: list[int], reflection_id: int
) -> None:
    """Mark the given signals as consumed by a reflection."""
    if not signal_ids:
        return
    with transaction(conn):
        placeholders = ",".join("?" for _ in signal_ids)
        conn.execute(
            f"UPDATE evolution_signals SET consumed_by = ? WHERE id IN ({placeholders})",
            [reflection_id, *signal_ids],
        )


def should_trigger_reflection(
    conn: sqlite3.Connection,
    threshold: float = 3.0,
    min_signals: int = 3,
) -> bool:
    """Return True if unconsumed signal magnitude exceeds threshold and count >= min_signals."""
    row = conn.execute(
        """SELECT COUNT(*) AS count, COALESCE(SUM(magnitude), 0.0) AS total_magnitude
           FROM evolution_signals WHERE consumed_by IS NULL"""
    ).fetchone()
    return row["count"] >= min_signals and row["total_magnitude"] >= threshold
