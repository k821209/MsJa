"""Shared test fixtures for deevo.ai.persona tests."""

import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "001_init.sql"


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite DB with the full schema applied."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    sql = SCHEMA_PATH.read_text()
    db.executescript(sql)

    yield db
    db.close()
