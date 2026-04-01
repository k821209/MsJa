"""Tests for src.reflection — reflection engine lifecycle."""

import json

import pytest

from src.reflection import (
    apply_reflection,
    build_reflection_prompt,
    complete_reflection,
    create_reflection,
    get_reflection_history,
    run_reflection,
)
from src.signals import get_unconsumed_signals, record_signal
from src.persona import get_current_traits, get_active_rules


def _add_signals(conn, n=3, magnitude=1.5):
    """Helper to insert N unconsumed signals."""
    ids = []
    for i in range(n):
        sid = record_signal(
            conn,
            signal_type="user_feedback",
            evidence=f"Test signal {i}",
            dimension="formality",
            direction=1.0,
            magnitude=magnitude,
        )
        ids.append(sid)
    return ids


# ── create_reflection ────────────────────────────────────────────


class TestCreateReflection:
    def test_creates_pending_reflection(self, conn):
        rid = create_reflection(conn, "manual")
        row = conn.execute(
            "SELECT * FROM reflections WHERE id = ?", (rid,)
        ).fetchone()
        assert row["status"] == "pending"
        assert row["trigger_type"] == "manual"

    def test_invalid_trigger_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            create_reflection(conn, "invalid_type")

    @pytest.mark.parametrize(
        "trigger",
        ["periodic", "threshold", "user_feedback", "goal_review", "manual"],
    )
    def test_all_valid_triggers(self, conn, trigger):
        rid = create_reflection(conn, trigger)
        assert rid > 0


# ── build_reflection_prompt ──────────────────────────────────────


class TestBuildReflectionPrompt:
    def test_returns_nonempty_string(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")
        prompt = build_reflection_prompt(conn, rid)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_trait_info(self, conn):
        rid = create_reflection(conn, "manual")
        prompt = build_reflection_prompt(conn, rid)
        assert "formality" in prompt
        assert "Current Traits" in prompt

    def test_contains_signals(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")
        prompt = build_reflection_prompt(conn, rid)
        assert "Test signal" in prompt
        assert "Evolution Signals" in prompt

    def test_sets_status_to_in_progress(self, conn):
        rid = create_reflection(conn, "manual")
        build_reflection_prompt(conn, rid)
        row = conn.execute(
            "SELECT status FROM reflections WHERE id = ?", (rid,)
        ).fetchone()
        assert row["status"] == "in_progress"


# ── apply_reflection ─────────────────────────────────────────────


class TestApplyReflection:
    def test_applies_trait_changes(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")

        decisions = {
            "analysis": "Test analysis",
            "trait_changes": {"formality": 0.02},
            "rule_changes": [],
            "goal_changes": [],
        }
        summary = apply_reflection(conn, rid, decisions)

        assert summary["traits"] is not None
        assert summary["traits"]["applied"]["formality"] == pytest.approx(0.02)

        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.52)

    def test_bounded_trait_changes(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")

        decisions = {
            "analysis": "Bounded test",
            "trait_changes": {"formality": 0.5},  # way over max_delta=0.05
            "rule_changes": [],
            "goal_changes": [],
        }
        summary = apply_reflection(conn, rid, decisions)
        assert summary["traits"]["bounded"] is True

    def test_adds_new_rule(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")

        decisions = {
            "analysis": "Rule test",
            "trait_changes": {},
            "rule_changes": [
                {"action": "add", "rule_text": "New reflection rule", "category": "test", "priority": 50}
            ],
            "goal_changes": [],
        }
        summary = apply_reflection(conn, rid, decisions)
        assert len(summary["rules_added"]) == 1

        rules = get_active_rules(conn, category="test")
        texts = [r["rule_text"] for r in rules]
        assert "New reflection rule" in texts

    def test_creates_new_goal(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")

        decisions = {
            "analysis": "Goal test",
            "trait_changes": {},
            "rule_changes": [],
            "goal_changes": [
                {
                    "action": "create",
                    "title": "Improve formality",
                    "description": "Target formality of 0.8",
                    "goal_type": "trait_target",
                    "source": "self",
                }
            ],
        }
        summary = apply_reflection(conn, rid, decisions)
        assert len(summary["goals_created"]) == 1

        goal = conn.execute(
            "SELECT * FROM goals WHERE id = ?", (summary["goals_created"][0],)
        ).fetchone()
        assert goal["title"] == "Improve formality"
        assert goal["status"] == "active"

    def test_consumes_signals(self, conn):
        _add_signals(conn, n=3)
        rid = create_reflection(conn, "manual")

        decisions = {"analysis": "Consume test", "trait_changes": {}, "rule_changes": [], "goal_changes": []}
        summary = apply_reflection(conn, rid, decisions)
        assert summary["signals_consumed"] == 3

        unconsumed = get_unconsumed_signals(conn)
        assert len(unconsumed) == 0

    def test_updates_reflection_status(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")

        decisions = {"analysis": "Status test", "trait_changes": {}, "rule_changes": [], "goal_changes": []}
        apply_reflection(conn, rid, decisions)

        row = conn.execute(
            "SELECT status, analysis_text, completed_at FROM reflections WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["status"] == "completed"
        assert row["analysis_text"] == "Status test"
        assert row["completed_at"] is not None


# ── complete_reflection ──────────────────────────────────────────


class TestCompleteReflection:
    def test_parses_valid_json(self, conn):
        _add_signals(conn)
        rid = create_reflection(conn, "manual")

        llm_response = json.dumps({
            "analysis": "Valid response",
            "trait_changes": {"humor": 0.01},
            "rule_changes": [],
            "goal_changes": [],
        })
        summary = complete_reflection(conn, rid, llm_response)
        assert summary["traits"]["applied"]["humor"] == pytest.approx(0.01)

    def test_invalid_json_raises_and_marks_failed(self, conn):
        rid = create_reflection(conn, "manual")

        with pytest.raises(ValueError, match="Invalid JSON"):
            complete_reflection(conn, rid, "not valid json {{{")

        row = conn.execute(
            "SELECT status FROM reflections WHERE id = ?", (rid,)
        ).fetchone()
        assert row["status"] == "failed"


# ── run_reflection ───────────────────────────────────────────────


class TestRunReflection:
    def test_manual_trigger_always_runs(self, conn):
        # No signals needed for manual
        result = run_reflection(conn, trigger_type="manual")
        assert result["reflection_id"] is not None
        assert result["prompt"] is not None

    def test_threshold_trigger_skips_when_insufficient(self, conn):
        # No signals -> should skip
        result = run_reflection(conn, trigger_type="periodic")
        assert result.get("skipped") is True
        assert result["reflection_id"] is None

    def test_threshold_trigger_runs_when_sufficient(self, conn):
        # Add enough signals to exceed threshold (3 signals, total mag 4.5 > 3.0)
        _add_signals(conn, n=3, magnitude=1.5)
        result = run_reflection(conn, trigger_type="periodic")
        assert result["reflection_id"] is not None
        assert result["signal_count"] == 3

    def test_user_feedback_trigger_skips_threshold(self, conn):
        # No signals but user_feedback bypasses threshold
        result = run_reflection(conn, trigger_type="user_feedback")
        assert result["reflection_id"] is not None


# ── get_reflection_history ───────────────────────────────────────


class TestGetReflectionHistory:
    def test_returns_recent_reflections(self, conn):
        rid = create_reflection(conn, "manual")
        decisions = {"analysis": "History test", "trait_changes": {}, "rule_changes": [], "goal_changes": []}
        apply_reflection(conn, rid, decisions)

        history = get_reflection_history(conn)
        assert len(history) >= 1
        assert history[0]["id"] == rid
        assert history[0]["status"] == "completed"

    def test_respects_limit(self, conn):
        for _ in range(5):
            rid = create_reflection(conn, "manual")
            apply_reflection(conn, rid, {"analysis": "", "trait_changes": {}, "rule_changes": [], "goal_changes": []})

        history = get_reflection_history(conn, limit=2)
        assert len(history) == 2
