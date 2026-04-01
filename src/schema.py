"""Schema inspection and validation utilities."""

from __future__ import annotations

import sqlite3


EXPECTED_TABLES = {
    "persona_meta",
    "trait_definitions",
    "trait_snapshots",
    "trait_snapshot_values",
    "trait_current",
    "behavioral_rules",
    "rule_changes",
    "memories",
    "memory_tags",
    "memory_embeddings",
    "memory_links",
    "goals",
    "goal_checkpoints",
    "reflections",
    "evolution_signals",
    "interactions",
    "schema_migrations",
}


def get_tables(conn: sqlite3.Connection) -> set[str]:
    """Return all user table names in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def validate_schema(conn: sqlite3.Connection) -> list[str]:
    """Check that all expected tables exist. Returns list of missing tables."""
    existing = get_tables(conn)
    return sorted(EXPECTED_TABLES - existing)


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from migrations table."""
    try:
        row = conn.execute("SELECT MAX(version) as v FROM schema_migrations").fetchone()
        return row["v"] or 0
    except sqlite3.OperationalError:
        return 0
