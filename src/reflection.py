"""Reflection engine — aggregates signals, builds LLM prompts, and applies evolution decisions."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.db import transaction
from src.persona import (
    add_rule,
    deactivate_rule,
    get_active_rules,
    get_persona_state,
    get_trait_definitions,
    update_rule_weight,
    update_traits,
)
from src.signals import (
    consume_signals,
    get_unconsumed_signals,
    should_trigger_reflection,
)

VALID_TRIGGER_TYPES = frozenset(
    {"periodic", "threshold", "user_feedback", "goal_review", "manual"}
)

# Trigger types that skip the should_trigger_reflection() check
FORCE_TRIGGERS = frozenset({"manual", "user_feedback"})


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# ── Reflection lifecycle ─────────────────────────────────────────


def create_reflection(conn: sqlite3.Connection, trigger_type: str) -> int:
    """Create a new reflection record with status='pending'. Returns the id."""
    if trigger_type not in VALID_TRIGGER_TYPES:
        raise ValueError(
            f"Invalid trigger_type '{trigger_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_TRIGGER_TYPES))}"
        )
    cursor = conn.execute(
        "INSERT INTO reflections (trigger_type, status) VALUES (?, 'pending')",
        (trigger_type,),
    )
    conn.commit()
    return cursor.lastrowid


def build_reflection_prompt(conn: sqlite3.Connection, reflection_id: int) -> str:
    """Build the LLM prompt for a reflection cycle.

    Gathers unconsumed signals, current persona state, active goals,
    recent interactions, and trait definitions, then returns a structured
    prompt requesting JSON analysis and proposals.
    """
    # 1. Unconsumed signals
    signals = get_unconsumed_signals(conn)

    # 2. Current persona state
    state = get_persona_state(conn)

    # 3. Active goals
    goal_rows = conn.execute(
        "SELECT * FROM goals WHERE status = 'active' ORDER BY created_at"
    ).fetchall()
    goals = [_row_to_dict(r) for r in goal_rows]

    # 4. Recent interactions
    interaction_rows = conn.execute(
        """SELECT id, started_at, ended_at, summary, user_satisfaction, turn_count
           FROM interactions ORDER BY started_at DESC LIMIT 10"""
    ).fetchall()
    interactions = [_row_to_dict(r) for r in interaction_rows]

    # 5. Trait definitions
    trait_defs = get_trait_definitions(conn)

    # Update reflection with the review window
    conn.execute(
        "UPDATE reflections SET status = 'in_progress', interactions_reviewed = ? WHERE id = ?",
        (len(interactions), reflection_id),
    )
    conn.commit()

    # Build prompt
    prompt = f"""You are the self-reflection engine for an AI persona named "{state['persona_name']}".
Analyze the accumulated evolution signals and propose bounded adjustments to traits, rules, and goals.

## Current Traits
{json.dumps(state['traits'], indent=2)}

## Trait Definitions (bounds)
{json.dumps(trait_defs, indent=2, default=str)}

## Active Behavioral Rules
{json.dumps(state['rules'], indent=2, default=str)}

## Active Goals
{json.dumps(goals, indent=2, default=str)}

## Recent Interactions (last {len(interactions)})
{json.dumps(interactions, indent=2, default=str)}

## Unconsumed Evolution Signals ({len(signals)} signals)
{json.dumps(signals, indent=2, default=str)}

## Instructions
Analyze the signals above and identify patterns. Then propose changes in the following JSON format:

```json
{{
  "analysis": "Your narrative analysis of the signals and what they indicate about needed persona changes.",
  "trait_changes": {{
    "trait_key": delta_value
  }},
  "rule_changes": [
    {{"action": "add", "rule_text": "...", "category": "...", "priority": 100}},
    {{"action": "deactivate", "rule_id": 123}},
    {{"action": "update_weight", "rule_id": 123, "new_weight": 0.8}}
  ],
  "goal_changes": [
    {{"action": "create", "title": "...", "description": "...", "goal_type": "...", "source": "self"}},
    {{"action": "update_progress", "goal_id": 123, "progress": 0.75, "notes": "..."}},
    {{"action": "complete", "goal_id": 123}},
    {{"action": "abandon", "goal_id": 123}}
  ]
}}
```

Rules:
- trait_changes values are DELTAS (not absolute values). They will be clamped by max_delta.
- Only propose changes supported by evidence in the signals.
- Be conservative — small incremental changes are preferred.
- Do not deactivate locked rules.
- Respond with ONLY the JSON object, no other text.
"""
    return prompt


def apply_reflection(
    conn: sqlite3.Connection, reflection_id: int, decisions: dict[str, Any]
) -> dict[str, Any]:
    """Apply parsed LLM decisions: trait changes, rule changes, goal changes.

    Returns a summary dict of what was actually applied.
    """
    summary: dict[str, Any] = {
        "traits": None,
        "rules_added": [],
        "rules_deactivated": [],
        "rules_weight_updated": [],
        "goals_created": [],
        "goals_updated": [],
        "signals_consumed": 0,
        "errors": [],
    }

    # 1. Apply trait changes
    trait_changes = decisions.get("trait_changes", {})
    if trait_changes:
        result = update_traits(
            conn,
            trait_changes,
            trigger="reflection",
            reflection_id=reflection_id,
            notes=decisions.get("analysis", ""),
        )
        summary["traits"] = result

    # 2. Process rule changes
    for rc in decisions.get("rule_changes", []):
        action = rc.get("action")
        try:
            if action == "add":
                rule_id = add_rule(
                    conn,
                    rule_text=rc["rule_text"],
                    category=rc.get("category", "general"),
                    priority=rc.get("priority", 100),
                    source="reflection",
                )
                summary["rules_added"].append(rule_id)
            elif action == "deactivate":
                deactivate_rule(
                    conn,
                    rule_id=rc["rule_id"],
                    changed_by="reflection",
                    reflection_id=reflection_id,
                )
                summary["rules_deactivated"].append(rc["rule_id"])
            elif action == "update_weight":
                update_rule_weight(
                    conn,
                    rule_id=rc["rule_id"],
                    new_weight=rc["new_weight"],
                    changed_by="reflection",
                    reflection_id=reflection_id,
                )
                summary["rules_weight_updated"].append(rc["rule_id"])
        except (ValueError, KeyError) as e:
            summary["errors"].append(f"Rule change error: {e}")

    # 3. Process goal changes
    for gc in decisions.get("goal_changes", []):
        action = gc.get("action")
        try:
            if action == "create":
                cursor = conn.execute(
                    """INSERT INTO goals (title, description, goal_type, source, reflection_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        gc["title"],
                        gc.get("description"),
                        gc.get("goal_type", "skill"),
                        gc.get("source", "self"),
                        reflection_id,
                    ),
                )
                conn.commit()
                summary["goals_created"].append(cursor.lastrowid)
            elif action == "update_progress":
                conn.execute(
                    """UPDATE goals SET progress = ? WHERE id = ? AND status = 'active'""",
                    (gc["progress"], gc["goal_id"]),
                )
                conn.execute(
                    """INSERT INTO goal_checkpoints (goal_id, progress, notes, reflection_id)
                       VALUES (?, ?, ?, ?)""",
                    (gc["goal_id"], gc["progress"], gc.get("notes"), reflection_id),
                )
                conn.commit()
                summary["goals_updated"].append(gc["goal_id"])
            elif action == "complete":
                conn.execute(
                    """UPDATE goals
                       SET status = 'completed', progress = 1.0,
                           completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                       WHERE id = ? AND status = 'active'""",
                    (gc["goal_id"],),
                )
                conn.commit()
                summary["goals_updated"].append(gc["goal_id"])
            elif action == "abandon":
                conn.execute(
                    "UPDATE goals SET status = 'abandoned' WHERE id = ? AND status = 'active'",
                    (gc["goal_id"],),
                )
                conn.commit()
                summary["goals_updated"].append(gc["goal_id"])
        except (ValueError, KeyError) as e:
            summary["errors"].append(f"Goal change error: {e}")

    # 4. Consume all unconsumed signals
    signals = get_unconsumed_signals(conn)
    signal_ids = [s["id"] for s in signals]
    if signal_ids:
        consume_signals(conn, signal_ids, reflection_id)
    summary["signals_consumed"] = len(signal_ids)

    # 5. Update reflection record
    analysis = decisions.get("analysis", "")
    was_bounded = 1 if (summary["traits"] and summary["traits"].get("bounded")) else 0

    conn.execute(
        """UPDATE reflections
           SET status = 'completed',
               decisions_json = ?,
               analysis_text = ?,
               was_bounded = ?,
               completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE id = ?""",
        (json.dumps(decisions), analysis, was_bounded, reflection_id),
    )
    conn.commit()

    return summary


# ── Orchestration ────────────────────────────────────────────────


def run_reflection(
    conn: sqlite3.Connection, trigger_type: str = "manual"
) -> dict[str, Any]:
    """Orchestrate the first half of a reflection cycle.

    Checks whether reflection is warranted, creates the record, and builds
    the LLM prompt. Does NOT call the LLM — returns the prompt so the
    caller can handle the LLM invocation.

    Returns:
        {"reflection_id": int, "prompt": str, "signal_count": int}
    """
    # Check threshold (skip for manual / user_feedback triggers)
    if trigger_type not in FORCE_TRIGGERS:
        if not should_trigger_reflection(conn):
            return {"reflection_id": None, "prompt": None, "signal_count": 0, "skipped": True}

    reflection_id = create_reflection(conn, trigger_type)
    signals = get_unconsumed_signals(conn)
    prompt = build_reflection_prompt(conn, reflection_id)

    return {
        "reflection_id": reflection_id,
        "prompt": prompt,
        "signal_count": len(signals),
    }


def complete_reflection(
    conn: sqlite3.Connection, reflection_id: int, llm_response: str
) -> dict[str, Any]:
    """Parse the LLM JSON response and apply the reflection decisions.

    Returns the application summary from apply_reflection().
    """
    try:
        decisions = json.loads(llm_response)
    except json.JSONDecodeError as e:
        # Mark reflection as failed
        conn.execute(
            """UPDATE reflections
               SET status = 'failed',
                   analysis_text = ?,
                   completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (f"Failed to parse LLM response: {e}", reflection_id),
        )
        conn.commit()
        raise ValueError(f"Invalid JSON in LLM response: {e}") from e

    return apply_reflection(conn, reflection_id, decisions)


# ── History ──────────────────────────────────────────────────────


def get_reflection_history(
    conn: sqlite3.Connection, limit: int = 10
) -> list[dict[str, Any]]:
    """Return recent reflections with their decisions summary."""
    rows = conn.execute(
        """SELECT id, trigger_type, status, interactions_reviewed,
                  analysis_text, was_bounded, user_approved,
                  created_at, completed_at
           FROM reflections
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
