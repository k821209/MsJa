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


# ── Personal Image ──────────────────────────────────────────────


def get_active_images(
    conn: sqlite3.Connection, image_type: str | None = None
) -> list[dict[str, Any]]:
    """Return active persona images, optionally filtered by type."""
    if image_type:
        rows = conn.execute(
            "SELECT * FROM persona_images WHERE is_active = 1 AND image_type = ? ORDER BY id",
            (image_type,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM persona_images WHERE is_active = 1 ORDER BY image_type, id"
        ).fetchall()
    return _rows_to_dicts(rows)


def add_image(
    conn: sqlite3.Connection,
    image_type: str,
    label: str,
    file_path: str,
    description: str | None = None,
) -> int:
    """Add a persona image reference. Returns image id."""
    valid_types = ("avatar", "expression", "scene")
    if image_type not in valid_types:
        raise ValueError(f"Invalid image_type '{image_type}'. Must be one of: {valid_types}")
    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO persona_images (image_type, label, file_path, description)
               VALUES (?, ?, ?, ?)""",
            (image_type, label, file_path, description),
        )
        return cursor.lastrowid


def set_avatar(conn: sqlite3.Connection, file_path: str) -> None:
    """Set the main avatar path in persona_meta."""
    conn.execute("UPDATE persona_meta SET avatar_path = ? WHERE id = 1", (file_path,))
    conn.commit()


def get_avatar(conn: sqlite3.Connection) -> str | None:
    """Get the current avatar path."""
    row = conn.execute("SELECT avatar_path FROM persona_meta WHERE id = 1").fetchone()
    return row["avatar_path"] if row else None


# ── Lore ────────────────────────────────────────────────────────


def get_active_lore(
    conn: sqlite3.Connection, category: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Return active lore entries, ordered by significance DESC."""
    if category:
        rows = conn.execute(
            """SELECT * FROM persona_lore
               WHERE is_active = 1 AND category = ?
               ORDER BY significance DESC LIMIT ?""",
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM persona_lore WHERE is_active = 1
               ORDER BY significance DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return _rows_to_dicts(rows)


def add_lore(
    conn: sqlite3.Connection,
    content: str,
    significance: float = 0.5,
    category: str = "identity",
    source: str = "user",
    parent_id: int | None = None,
    reflection_id: int | None = None,
) -> int:
    """Add a new lore entry. Returns lore id."""
    valid_categories = ("identity", "philosophy", "behavior", "aesthetic", "voice")
    if category not in valid_categories:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {valid_categories}")
    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO persona_lore
               (content, significance, category, source, parent_id, reflection_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content, min(1.0, max(0.0, significance)), category, source,
             parent_id, reflection_id),
        )
        lore_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO lore_changes (lore_id, change_type, new_value, changed_by, reflection_id)
               VALUES (?, 'created', ?, ?, ?)""",
            (lore_id, content, source, reflection_id),
        )
        return lore_id


def evolve_lore(
    conn: sqlite3.Connection,
    parent_id: int,
    new_content: str,
    significance: float | None = None,
    reflection_id: int | None = None,
) -> int:
    """Evolve a lore entry: archive the old one and create a new version.

    Returns the new lore id.
    """
    with transaction(conn):
        parent = conn.execute(
            "SELECT * FROM persona_lore WHERE id = ?", (parent_id,)
        ).fetchone()
        if parent is None:
            raise ValueError(f"Lore {parent_id} not found")

        # Archive old
        conn.execute(
            """UPDATE persona_lore
               SET is_active = 0, archived_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (parent_id,),
        )
        conn.execute(
            """INSERT INTO lore_changes (lore_id, change_type, old_value, changed_by, reflection_id)
               VALUES (?, 'evolved', ?, 'reflection', ?)""",
            (parent_id, parent["content"], reflection_id),
        )

        # Create evolved version
        new_sig = significance if significance is not None else parent["significance"]
        cursor = conn.execute(
            """INSERT INTO persona_lore
               (content, significance, category, source, parent_id, reflection_id)
               VALUES (?, ?, ?, 'reflection', ?, ?)""",
            (new_content, min(1.0, max(0.0, new_sig)), parent["category"],
             parent_id, reflection_id),
        )
        new_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO lore_changes (lore_id, change_type, new_value, changed_by, reflection_id)
               VALUES (?, 'created', ?, 'reflection', ?)""",
            (new_id, new_content, reflection_id),
        )
        return new_id


def archive_lore(
    conn: sqlite3.Connection,
    lore_id: int,
    changed_by: str = "user",
    reflection_id: int | None = None,
) -> None:
    """Archive a lore entry."""
    with transaction(conn):
        conn.execute(
            """UPDATE persona_lore
               SET is_active = 0, archived_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (lore_id,),
        )
        conn.execute(
            """INSERT INTO lore_changes (lore_id, change_type, changed_by, reflection_id)
               VALUES (?, 'archived', ?, ?)""",
            (lore_id, changed_by, reflection_id),
        )


def update_lore_significance(
    conn: sqlite3.Connection,
    lore_id: int,
    new_significance: float,
    changed_by: str = "reflection",
    reflection_id: int | None = None,
) -> None:
    """Update significance score of a lore entry."""
    new_significance = min(1.0, max(0.0, new_significance))
    with transaction(conn):
        row = conn.execute(
            "SELECT significance FROM persona_lore WHERE id = ?", (lore_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Lore {lore_id} not found")
        conn.execute(
            "UPDATE persona_lore SET significance = ? WHERE id = ?",
            (new_significance, lore_id),
        )
        conn.execute(
            """INSERT INTO lore_changes
               (lore_id, change_type, old_value, new_value, changed_by, reflection_id)
               VALUES (?, 'significance_changed', ?, ?, ?, ?)""",
            (lore_id, str(row["significance"]), str(new_significance),
             changed_by, reflection_id),
        )


def get_lore_history(conn: sqlite3.Connection, lore_id: int) -> list[dict[str, Any]]:
    """Trace the evolution chain of a lore entry back to its origin."""
    chain = []
    current_id = lore_id
    while current_id is not None:
        row = conn.execute(
            "SELECT * FROM persona_lore WHERE id = ?", (current_id,)
        ).fetchone()
        if row is None:
            break
        chain.append(_row_to_dict(row))
        current_id = row["parent_id"]
    return chain


# ── Composite State ──────────────────────────────────────────────


def get_persona_state(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return the full persona state: traits, rules, lore, name, and images."""
    meta = conn.execute(
        "SELECT persona_name, avatar_path FROM persona_meta WHERE id = 1"
    ).fetchone()
    images = get_active_images(conn)
    lore = get_active_lore(conn)
    return {
        "persona_name": meta["persona_name"] if meta else "deevo",
        "avatar": meta["avatar_path"] if meta else None,
        "traits": get_current_traits(conn),
        "rules": get_active_rules(conn),
        "lore": lore,
        "images": images,
    }
