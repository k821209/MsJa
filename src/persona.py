"""Persona state manager — CRUD for traits and behavioral rules."""

from __future__ import annotations

import sqlite3
from typing import Any

from src.db import transaction


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert a list of sqlite3.Row to plain dicts."""
    return [_row_to_dict(r) for r in rows]


# ── Traits ───────────────────────────────────────────────────────


def get_current_traits(conn: sqlite3.Connection) -> dict[str, float]:
    """Return current trait values as {trait_key: value}."""
    rows = conn.execute("SELECT trait_key, value FROM trait_current").fetchall()
    return {row["trait_key"]: row["value"] for row in rows}


def get_trait_definitions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all trait definitions with bounds."""
    rows = conn.execute("SELECT * FROM trait_definitions").fetchall()
    return _rows_to_dicts(rows)


def get_trait_history(
    conn: sqlite3.Connection, trait_key: str, limit: int = 20
) -> list[dict[str, Any]]:
    """Return snapshots for a specific trait over time, most recent first."""
    rows = conn.execute(
        """
        SELECT ts.id AS snapshot_id, ts.taken_at, ts.trigger, ts.notes,
               tsv.value, tsv.delta, tsv.reason
        FROM trait_snapshot_values tsv
        JOIN trait_snapshots ts ON ts.id = tsv.snapshot_id
        WHERE tsv.trait_key = ?
        ORDER BY ts.id DESC
        LIMIT ?
        """,
        (trait_key, limit),
    ).fetchall()
    return _rows_to_dicts(rows)


def update_traits(
    conn: sqlite3.Connection,
    changes: dict[str, float],
    trigger: str,
    reflection_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Apply bounded trait changes atomically.

    Returns a dict with keys:
        applied: {trait_key: actual_delta}
        bounded: bool — True if any delta or value was clamped
    """
    with transaction(conn):
        # Load definitions and current values
        defs = {
            row["trait_key"]: _row_to_dict(row)
            for row in conn.execute("SELECT * FROM trait_definitions").fetchall()
        }
        current = get_current_traits(conn)

        # Create snapshot
        cursor = conn.execute(
            "INSERT INTO trait_snapshots (trigger, reflection_id, notes) VALUES (?, ?, ?)",
            (trigger, reflection_id, notes),
        )
        snapshot_id = cursor.lastrowid

        applied: dict[str, float] = {}
        bounded = False

        for trait_key, raw_delta in changes.items():
            if trait_key not in defs:
                raise ValueError(f"Unknown trait: {trait_key}")

            d = defs[trait_key]
            min_val, max_val, max_delta = d["min_value"], d["max_value"], d["max_delta"]
            cur_val = current.get(trait_key, d["default_value"])

            # Clamp delta by max_delta
            clamped_delta = max(-max_delta, min(max_delta, raw_delta))
            if clamped_delta != raw_delta:
                bounded = True

            # Clamp result by [min, max]
            new_val = cur_val + clamped_delta
            if new_val < min_val:
                new_val = min_val
                bounded = True
            elif new_val > max_val:
                new_val = max_val
                bounded = True

            actual_delta = new_val - cur_val
            applied[trait_key] = actual_delta

            # Record snapshot value
            conn.execute(
                """INSERT INTO trait_snapshot_values (snapshot_id, trait_key, value, delta)
                   VALUES (?, ?, ?, ?)""",
                (snapshot_id, trait_key, new_val, actual_delta),
            )

            # Upsert trait_current
            conn.execute(
                """INSERT INTO trait_current (trait_key, value, updated_at, snapshot_id)
                   VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)
                   ON CONFLICT(trait_key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = excluded.updated_at,
                       snapshot_id = excluded.snapshot_id""",
                (trait_key, new_val, snapshot_id),
            )

    return {"applied": applied, "bounded": bounded}


def override_trait(
    conn: sqlite3.Connection, trait_key: str, value: float
) -> None:
    """User override — bypasses max_delta but respects min/max bounds."""
    with transaction(conn):
        row = conn.execute(
            "SELECT * FROM trait_definitions WHERE trait_key = ?", (trait_key,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown trait: {trait_key}")

        d = _row_to_dict(row)
        clamped = max(d["min_value"], min(d["max_value"], value))

        current_row = conn.execute(
            "SELECT value FROM trait_current WHERE trait_key = ?", (trait_key,)
        ).fetchone()
        old_val = current_row["value"] if current_row else d["default_value"]
        delta = clamped - old_val

        cursor = conn.execute(
            "INSERT INTO trait_snapshots (trigger, notes) VALUES ('user_override', ?)",
            (f"User override: {trait_key} -> {clamped}",),
        )
        snapshot_id = cursor.lastrowid

        conn.execute(
            """INSERT INTO trait_snapshot_values (snapshot_id, trait_key, value, delta)
               VALUES (?, ?, ?, ?)""",
            (snapshot_id, trait_key, clamped, delta),
        )

        conn.execute(
            """INSERT INTO trait_current (trait_key, value, updated_at, snapshot_id)
               VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)
               ON CONFLICT(trait_key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at,
                   snapshot_id = excluded.snapshot_id""",
            (trait_key, clamped, snapshot_id),
        )


# ── Behavioral Rules ─────────────────────────────────────────────


def get_active_rules(
    conn: sqlite3.Connection, category: str | None = None
) -> list[dict[str, Any]]:
    """Return active rules, optionally filtered by category, ordered by priority."""
    if category is not None:
        rows = conn.execute(
            """SELECT * FROM behavioral_rules
               WHERE is_active = 1 AND category = ?
               ORDER BY priority""",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM behavioral_rules WHERE is_active = 1 ORDER BY priority"
        ).fetchall()
    return _rows_to_dicts(rows)


def add_rule(
    conn: sqlite3.Connection,
    rule_text: str,
    category: str,
    priority: int,
    source: str,
    is_locked: bool = False,
) -> int:
    """Create a new behavioral rule and log the change. Returns the rule id."""
    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO behavioral_rules (rule_text, category, priority, source, is_locked)
               VALUES (?, ?, ?, ?, ?)""",
            (rule_text, category, priority, source, int(is_locked)),
        )
        rule_id = cursor.lastrowid

        conn.execute(
            """INSERT INTO rule_changes (rule_id, change_type, new_value, changed_by)
               VALUES (?, 'created', ?, ?)""",
            (rule_id, rule_text, source),
        )

    return rule_id


def deactivate_rule(
    conn: sqlite3.Connection,
    rule_id: int,
    changed_by: str,
    reflection_id: int | None = None,
) -> None:
    """Deactivate a rule. Raises ValueError if the rule is locked."""
    with transaction(conn):
        row = conn.execute(
            "SELECT is_locked, is_active FROM behavioral_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Rule {rule_id} not found")
        if row["is_locked"]:
            raise ValueError(f"Rule {rule_id} is locked and cannot be deactivated")
        if not row["is_active"]:
            return  # already inactive

        conn.execute(
            """UPDATE behavioral_rules
               SET is_active = 0, deactivated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (rule_id,),
        )

        conn.execute(
            """INSERT INTO rule_changes (rule_id, change_type, changed_by, reflection_id)
               VALUES (?, 'deactivated', ?, ?)""",
            (rule_id, changed_by, reflection_id),
        )


def update_rule_weight(
    conn: sqlite3.Connection,
    rule_id: int,
    new_weight: float,
    changed_by: str,
    reflection_id: int | None = None,
) -> None:
    """Update a rule's weight and log the change."""
    with transaction(conn):
        row = conn.execute(
            "SELECT weight FROM behavioral_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Rule {rule_id} not found")

        old_weight = row["weight"]

        conn.execute(
            "UPDATE behavioral_rules SET weight = ? WHERE id = ?",
            (new_weight, rule_id),
        )

        conn.execute(
            """INSERT INTO rule_changes
               (rule_id, change_type, old_value, new_value, changed_by, reflection_id)
               VALUES (?, 'weight_changed', ?, ?, ?, ?)""",
            (rule_id, str(old_weight), str(new_weight), changed_by, reflection_id),
        )


# ── Composite State ──────────────────────────────────────────────


def get_persona_state(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return the full persona state: traits, rules, and name."""
    meta = conn.execute("SELECT persona_name FROM persona_meta WHERE id = 1").fetchone()
    return {
        "persona_name": meta["persona_name"] if meta else "deevo",
        "traits": get_current_traits(conn),
        "rules": get_active_rules(conn),
    }
