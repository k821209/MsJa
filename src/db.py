"""SQLite connection manager with migration support."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "persona.db"
SCHEMA_DIR = Path(__file__).parent.parent / "schema"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create a new SQLite connection with recommended settings."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Context manager for atomic transactions."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_current_version(conn: sqlite3.Connection) -> int:
    """Get the latest applied schema version."""
    try:
        row = conn.execute(
            "SELECT MAX(version) as v FROM schema_migrations"
        ).fetchone()
        return row["v"] or 0
    except sqlite3.OperationalError:
        return 0


def run_migrations(conn: sqlite3.Connection, schema_dir: Path = SCHEMA_DIR) -> list[str]:
    """Apply pending SQL migrations in order. Returns list of applied migration names."""
    current = get_current_version(conn)
    applied = []

    migration_files = sorted(schema_dir.glob("*.sql"))
    for migration_file in migration_files:
        # Extract version number from filename like "001_init.sql"
        version = int(migration_file.stem.split("_")[0])
        if version <= current:
            continue

        sql = migration_file.read_text()
        conn.executescript(sql)
        applied.append(migration_file.name)

    return applied


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Initialize database: create if needed, run migrations, return connection."""
    conn = get_connection(db_path)
    applied = run_migrations(conn)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    return conn
