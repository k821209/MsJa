"""Tests for src.persona — trait and rule CRUD."""

import pytest

from src.persona import (
    add_rule,
    deactivate_rule,
    get_active_rules,
    get_current_traits,
    get_persona_state,
    get_trait_definitions,
    get_trait_history,
    override_trait,
    update_rule_weight,
    update_traits,
)


# ── Traits ───────────────────────────────────────────────────────


class TestGetCurrentTraits:
    def test_seed_traits_loaded(self, conn):
        traits = get_current_traits(conn)
        assert len(traits) == 7
        expected_keys = {
            "formality", "verbosity", "empathy", "humor",
            "proactiveness", "assertiveness", "creativity",
        }
        assert set(traits.keys()) == expected_keys

    def test_seed_default_values(self, conn):
        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.5)
        assert traits["verbosity"] == pytest.approx(0.4)
        assert traits["empathy"] == pytest.approx(0.6)
        assert traits["humor"] == pytest.approx(0.3)


class TestUpdateTraits:
    def test_normal_update_within_bounds(self, conn):
        result = update_traits(conn, {"formality": 0.02}, trigger="reflection")
        assert result["bounded"] is False
        assert result["applied"]["formality"] == pytest.approx(0.02)

        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.52)

    def test_delta_clamped_by_max_delta(self, conn):
        # formality max_delta = 0.05, request 0.2
        result = update_traits(conn, {"formality": 0.2}, trigger="reflection")
        assert result["bounded"] is True
        assert result["applied"]["formality"] == pytest.approx(0.05)

        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.55)

    def test_negative_delta_clamped(self, conn):
        # empathy max_delta = 0.03, request -0.1
        result = update_traits(conn, {"empathy": -0.1}, trigger="reflection")
        assert result["bounded"] is True
        assert result["applied"]["empathy"] == pytest.approx(-0.03)

    def test_result_clamped_by_max_value(self, conn):
        # Set formality close to max (1.0), then push over
        override_trait(conn, "formality", 0.98)
        result = update_traits(conn, {"formality": 0.05}, trigger="reflection")
        assert result["bounded"] is True
        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(1.0)

    def test_result_clamped_by_min_value(self, conn):
        override_trait(conn, "humor", 0.01)
        result = update_traits(conn, {"humor": -0.03}, trigger="reflection")
        assert result["bounded"] is True
        traits = get_current_traits(conn)
        assert traits["humor"] == pytest.approx(0.0)

    def test_unknown_trait_raises(self, conn):
        with pytest.raises(ValueError, match="Unknown trait"):
            update_traits(conn, {"nonexistent": 0.1}, trigger="reflection")

    def test_multiple_traits_at_once(self, conn):
        result = update_traits(
            conn,
            {"formality": 0.01, "humor": 0.02},
            trigger="reflection",
        )
        assert "formality" in result["applied"]
        assert "humor" in result["applied"]


class TestOverrideTrait:
    def test_override_sets_value(self, conn):
        override_trait(conn, "formality", 0.9)
        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.9)

    def test_override_bypasses_max_delta(self, conn):
        # formality max_delta=0.05, default=0.5 -> jumping to 0.9 is +0.4
        override_trait(conn, "formality", 0.9)
        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.9)

    def test_override_respects_max(self, conn):
        override_trait(conn, "formality", 5.0)
        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(1.0)

    def test_override_respects_min(self, conn):
        override_trait(conn, "formality", -5.0)
        traits = get_current_traits(conn)
        assert traits["formality"] == pytest.approx(0.0)

    def test_override_unknown_trait_raises(self, conn):
        with pytest.raises(ValueError, match="Unknown trait"):
            override_trait(conn, "nonexistent", 0.5)


class TestGetTraitHistory:
    def test_history_after_updates(self, conn):
        update_traits(conn, {"formality": 0.01}, trigger="reflection")
        update_traits(conn, {"formality": 0.02}, trigger="reflection")

        history = get_trait_history(conn, "formality")
        # At least 3 entries: init + 2 updates
        assert len(history) >= 3
        # Most recent first (ordered by snapshot id DESC)
        assert history[0]["delta"] == pytest.approx(0.02)
        assert history[1]["delta"] == pytest.approx(0.01)

    def test_history_respects_limit(self, conn):
        for _ in range(5):
            update_traits(conn, {"formality": 0.01}, trigger="reflection")
        history = get_trait_history(conn, "formality", limit=2)
        assert len(history) == 2


# ── Behavioral Rules ─────────────────────────────────────────────


class TestAddRule:
    def test_creates_rule_and_returns_id(self, conn):
        rule_id = add_rule(conn, "Test rule", "general", 50, "user")
        assert isinstance(rule_id, int)
        assert rule_id > 0

    def test_rule_appears_in_active_rules(self, conn):
        add_rule(conn, "New test rule", "testing", 99, "user")
        rules = get_active_rules(conn, category="testing")
        texts = [r["rule_text"] for r in rules]
        assert "New test rule" in texts

    def test_change_logged(self, conn):
        rule_id = add_rule(conn, "Logged rule", "general", 50, "user")
        row = conn.execute(
            "SELECT * FROM rule_changes WHERE rule_id = ? AND change_type = 'created'",
            (rule_id,),
        ).fetchone()
        assert row is not None
        assert row["new_value"] == "Logged rule"


class TestDeactivateRule:
    def test_deactivate_unlocked_rule(self, conn):
        rule_id = add_rule(conn, "Temp rule", "general", 50, "user")
        deactivate_rule(conn, rule_id, changed_by="user")

        rules = get_active_rules(conn)
        ids = [r["id"] for r in rules]
        assert rule_id not in ids

    def test_deactivate_locked_rule_raises(self, conn):
        # Seed rule id=1 is locked
        with pytest.raises(ValueError, match="locked"):
            deactivate_rule(conn, 1, changed_by="user")

    def test_deactivate_nonexistent_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            deactivate_rule(conn, 9999, changed_by="user")


class TestUpdateRuleWeight:
    def test_updates_weight(self, conn):
        rule_id = add_rule(conn, "Weight rule", "general", 50, "user")
        update_rule_weight(conn, rule_id, 0.7, changed_by="user")

        row = conn.execute(
            "SELECT weight FROM behavioral_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        assert row["weight"] == pytest.approx(0.7)

    def test_change_logged(self, conn):
        rule_id = add_rule(conn, "Weight log rule", "general", 50, "user")
        update_rule_weight(conn, rule_id, 0.3, changed_by="reflection")

        row = conn.execute(
            "SELECT * FROM rule_changes WHERE rule_id = ? AND change_type = 'weight_changed'",
            (rule_id,),
        ).fetchone()
        assert row is not None
        assert row["new_value"] == "0.3"
        assert row["old_value"] == "1.0"

    def test_nonexistent_rule_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            update_rule_weight(conn, 9999, 0.5, changed_by="user")


# ── Composite State ──────────────────────────────────────────────


class TestGetPersonaState:
    def test_returns_expected_keys(self, conn):
        state = get_persona_state(conn)
        assert "persona_name" in state
        assert "traits" in state
        assert "rules" in state

    def test_persona_name_is_deevo(self, conn):
        state = get_persona_state(conn)
        assert state["persona_name"] == "deevo"

    def test_traits_are_dict(self, conn):
        state = get_persona_state(conn)
        assert isinstance(state["traits"], dict)
        assert len(state["traits"]) == 7

    def test_rules_are_list(self, conn):
        state = get_persona_state(conn)
        assert isinstance(state["rules"], list)
        assert len(state["rules"]) >= 6  # seed rules
