"""Tests for src/memory.py — memory CRUD, links, interactions, and stats."""

import json

import pytest

from src.memory import (
    add_memory,
    archive_memory,
    delete_memory,
    end_interaction,
    get_linked_memories,
    get_memory,
    get_memory_stats,
    link_memories,
    query_memories,
    start_interaction,
)


# ── add_memory ───────────────────────────────────────────────


class TestAddMemory:
    def test_creates_new_memory(self, conn):
        mid = add_memory(conn, "episodic", "Had a meeting about Q3 planning")
        assert isinstance(mid, int)
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["memory_type"] == "episodic"
        assert row["content"] == "Had a meeting about Q3 planning"
        assert row["importance"] == 0.5
        assert row["content_hash"] is not None

    def test_custom_importance(self, conn):
        mid = add_memory(conn, "semantic", "Python is a language", importance=0.9)
        row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 0.9

    def test_tags_stored(self, conn):
        mid = add_memory(conn, "episodic", "Lunch with Alice", tags=["meeting", "social"])
        tags = conn.execute(
            "SELECT tag FROM memory_tags WHERE memory_id = ? ORDER BY tag", (mid,)
        ).fetchall()
        assert [t["tag"] for t in tags] == ["meeting", "social"]

    def test_dedup_boosts_existing(self, conn):
        content = "The earth orbits the sun"
        mid1 = add_memory(conn, "semantic", content, importance=0.5)
        mid2 = add_memory(conn, "semantic", content)
        assert mid1 == mid2

        row = conn.execute("SELECT importance, confidence FROM memories WHERE id = ?", (mid1,)).fetchone()
        assert row["importance"] == pytest.approx(0.6)
        assert row["confidence"] == pytest.approx(1.0)  # was 1.0, capped at 1.0

    def test_dedup_caps_at_one(self, conn):
        content = "Capped content"
        add_memory(conn, "semantic", content, importance=0.95)
        add_memory(conn, "semantic", content)
        row = conn.execute(
            "SELECT importance FROM memories WHERE content_hash IS NOT NULL AND content = ?",
            (content,),
        ).fetchone()
        assert row["importance"] == pytest.approx(1.0)

    def test_invalid_type_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid memory_type"):
            add_memory(conn, "invalid_type", "some content")

    def test_interaction_id_stored(self, conn):
        start_interaction(conn, "int-001")
        mid = add_memory(conn, "episodic", "During interaction", interaction_id="int-001")
        row = conn.execute("SELECT source_interaction_id FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["source_interaction_id"] == "int-001"


# ── get_memory ───────────────────────────────────────────────


class TestGetMemory:
    def test_returns_memory_with_tags(self, conn):
        mid = add_memory(conn, "semantic", "Fact about cats", tags=["animals", "facts"])
        result = get_memory(conn, mid)
        assert result is not None
        assert result["content"] == "Fact about cats"
        assert sorted(result["tags"]) == ["animals", "facts"]

    def test_increments_access_count(self, conn):
        mid = add_memory(conn, "episodic", "First access test")
        r1 = get_memory(conn, mid)
        assert r1["access_count"] == 1
        r2 = get_memory(conn, mid)
        assert r2["access_count"] == 2

    def test_returns_none_for_missing(self, conn):
        assert get_memory(conn, 99999) is None


# ── query_memories ───────────────────────────────────────────


class TestQueryMemories:
    def test_filter_by_type(self, conn):
        add_memory(conn, "episodic", "Ep memory")
        add_memory(conn, "semantic", "Sem memory")
        results = query_memories(conn, memory_type="episodic")
        assert all(r["memory_type"] == "episodic" for r in results)
        assert len(results) == 1

    def test_filter_by_tags_and_logic(self, conn):
        add_memory(conn, "episodic", "Tagged both", tags=["a", "b"])
        add_memory(conn, "episodic", "Tagged one", tags=["a"])
        results = query_memories(conn, tags=["a", "b"])
        assert len(results) == 1
        assert results[0]["content"] == "Tagged both"

    def test_like_search(self, conn):
        add_memory(conn, "semantic", "Python is great for data science")
        add_memory(conn, "semantic", "Java is compiled")
        results = query_memories(conn, query="Python")
        assert len(results) == 1
        assert "Python" in results[0]["content"]

    def test_ordered_by_importance_desc(self, conn):
        add_memory(conn, "semantic", "Low", importance=0.1)
        add_memory(conn, "semantic", "High", importance=0.9)
        add_memory(conn, "semantic", "Mid", importance=0.5)
        results = query_memories(conn, memory_type="semantic")
        importances = [r["importance"] for r in results]
        assert importances == sorted(importances, reverse=True)

    def test_excludes_archived_by_default(self, conn):
        mid = add_memory(conn, "episodic", "Will be archived")
        add_memory(conn, "episodic", "Stays active")
        archive_memory(conn, mid)
        results = query_memories(conn, memory_type="episodic")
        assert len(results) == 1
        assert results[0]["content"] == "Stays active"

    def test_include_archived(self, conn):
        mid = add_memory(conn, "episodic", "Archived one")
        add_memory(conn, "episodic", "Active one")
        archive_memory(conn, mid)
        results = query_memories(conn, memory_type="episodic", include_archived=True)
        assert len(results) == 2

    def test_results_include_tags(self, conn):
        add_memory(conn, "semantic", "Tagged mem", tags=["x", "y"])
        results = query_memories(conn, memory_type="semantic")
        assert sorted(results[0]["tags"]) == ["x", "y"]


# ── archive_memory ───────────────────────────────────────────


class TestArchiveMemory:
    def test_sets_archived_flag(self, conn):
        mid = add_memory(conn, "episodic", "To archive")
        archive_memory(conn, mid)
        row = conn.execute("SELECT is_archived FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["is_archived"] == 1


# ── delete_memory ────────────────────────────────────────────


class TestDeleteMemory:
    def test_hard_deletes_memory_and_tags(self, conn):
        mid = add_memory(conn, "episodic", "To delete", tags=["temp"])
        delete_memory(conn, mid)
        assert conn.execute("SELECT * FROM memories WHERE id = ?", (mid,)).fetchone() is None
        assert conn.execute("SELECT * FROM memory_tags WHERE memory_id = ?", (mid,)).fetchone() is None

    def test_hard_deletes_associated_links(self, conn):
        m1 = add_memory(conn, "semantic", "Source mem")
        m2 = add_memory(conn, "semantic", "Target mem")
        link_memories(conn, m1, m2, "supports")
        delete_memory(conn, m1)
        links = conn.execute(
            "SELECT * FROM memory_links WHERE source_id = ? OR target_id = ?", (m1, m1)
        ).fetchall()
        assert len(links) == 0


# ── link_memories ────────────────────────────────────────────


class TestLinkMemories:
    def test_creates_link(self, conn):
        m1 = add_memory(conn, "semantic", "Original fact")
        m2 = add_memory(conn, "semantic", "Derived fact")
        link_memories(conn, m1, m2, "derived_from")
        row = conn.execute(
            "SELECT * FROM memory_links WHERE source_id = ? AND target_id = ?", (m1, m2)
        ).fetchone()
        assert row is not None
        assert row["relation"] == "derived_from"

    def test_invalid_relation_raises(self, conn):
        m1 = add_memory(conn, "semantic", "Mem A")
        m2 = add_memory(conn, "semantic", "Mem B")
        with pytest.raises(ValueError, match="Invalid relation"):
            link_memories(conn, m1, m2, "unknown_relation")

    def test_all_valid_relations(self, conn):
        m1 = add_memory(conn, "semantic", "Base")
        for rel in ("derived_from", "contradicts", "supports", "supersedes"):
            m2 = add_memory(conn, "semantic", f"Related by {rel}")
            link_memories(conn, m1, m2, rel)
        links = conn.execute(
            "SELECT * FROM memory_links WHERE source_id = ?", (m1,)
        ).fetchall()
        assert len(links) == 4


# ── get_linked_memories ──────────────────────────────────────


class TestGetLinkedMemories:
    def test_returns_linked_with_relation(self, conn):
        m1 = add_memory(conn, "semantic", "Main fact")
        m2 = add_memory(conn, "semantic", "Supporting fact")
        link_memories(conn, m1, m2, "supports")
        linked = get_linked_memories(conn, m1)
        assert len(linked) == 1
        assert linked[0]["content"] == "Supporting fact"
        assert linked[0]["relation"] == "supports"

    def test_bidirectional_lookup(self, conn):
        m1 = add_memory(conn, "semantic", "Fact A")
        m2 = add_memory(conn, "semantic", "Fact B")
        link_memories(conn, m1, m2, "contradicts")
        # Both directions should find the link
        assert len(get_linked_memories(conn, m1)) == 1
        assert len(get_linked_memories(conn, m2)) == 1

    def test_includes_tags(self, conn):
        m1 = add_memory(conn, "semantic", "Source")
        m2 = add_memory(conn, "semantic", "Target", tags=["important"])
        link_memories(conn, m1, m2, "supports")
        linked = get_linked_memories(conn, m1)
        assert "important" in linked[0]["tags"]


# ── start_interaction / end_interaction ──────────────────────


class TestInteractions:
    def test_start_creates_record(self, conn):
        iid = start_interaction(conn, "test-int-001")
        assert iid == "test-int-001"
        row = conn.execute("SELECT * FROM interactions WHERE id = ?", (iid,)).fetchone()
        assert row is not None
        assert row["started_at"] is not None
        assert row["ended_at"] is None

    def test_end_updates_record(self, conn):
        iid = start_interaction(conn, "test-int-002")
        end_interaction(
            conn, iid,
            summary="Discussed project timeline",
            turn_count=5,
            traits_used={"formality": 0.7},
            rules_applied=[1, 3],
        )
        row = conn.execute("SELECT * FROM interactions WHERE id = ?", (iid,)).fetchone()
        assert row["ended_at"] is not None
        assert row["summary"] == "Discussed project timeline"
        assert row["turn_count"] == 5
        assert json.loads(row["traits_used"]) == {"formality": 0.7}
        assert json.loads(row["rules_applied"]) == [1, 3]

    def test_end_with_none_optional_fields(self, conn):
        iid = start_interaction(conn, "test-int-003")
        end_interaction(conn, iid)
        row = conn.execute("SELECT * FROM interactions WHERE id = ?", (iid,)).fetchone()
        assert row["ended_at"] is not None
        assert row["summary"] is None
        assert row["traits_used"] is None
        assert row["rules_applied"] is None


# ── get_memory_stats ─────────────────────────────────────────


class TestGetMemoryStats:
    def test_empty_db(self, conn):
        stats = get_memory_stats(conn)
        assert stats == {"total": 0, "by_type": {}, "active": 0, "archived": 0}

    def test_counts_by_type(self, conn):
        add_memory(conn, "episodic", "Ep 1")
        add_memory(conn, "episodic", "Ep 2")
        add_memory(conn, "semantic", "Sem 1")
        add_memory(conn, "procedural", "Proc 1")
        stats = get_memory_stats(conn)
        assert stats["total"] == 4
        assert stats["by_type"] == {"episodic": 2, "semantic": 1, "procedural": 1}
        assert stats["active"] == 4
        assert stats["archived"] == 0

    def test_archived_counted(self, conn):
        m1 = add_memory(conn, "episodic", "Active mem")
        m2 = add_memory(conn, "episodic", "Archived mem")
        archive_memory(conn, m2)
        stats = get_memory_stats(conn)
        assert stats["total"] == 2
        assert stats["active"] == 1
        assert stats["archived"] == 1
