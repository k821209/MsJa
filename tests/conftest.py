"""Shared test fixtures for deevo.ai.persona tests."""

import sqlite3
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).parent.parent / "schema"


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite DB with all migrations applied."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    for migration_file in sorted(SCHEMA_DIR.glob("*.sql")):
        sql = migration_file.read_text()
        db.executescript(sql)

    yield db
    db.close()
