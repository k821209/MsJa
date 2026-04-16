"""Analyze current context and produce an avatar generation prompt."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Allow running as `python src/avatar_context.py` (not just `python -m src.avatar_context`)
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection
from src.persona import get_avatar, get_persona_state
from src.signals import get_unconsumed_signals


def get_current_context(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Return a summary of the current context for avatar generation."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        now = datetime.now()

        # Time of day
        hour = now.hour
        if 5 <= hour < 9:
            time_period = "early_morning"
            time_desc = "이른 아침"
        elif 9 <= hour < 12:
            time_period = "morning"
            time_desc = "오전"
        elif 12 <= hour < 14:
            time_period = "lunch"
            time_desc = "점심시간"
        elif 14 <= hour < 18:
            time_period = "afternoon"
            time_desc = "오후"
        elif 18 <= hour < 21:
            time_period = "evening"
            time_desc = "저녁"
        elif 21 <= hour or hour < 2:
            time_period = "night"
            time_desc = "밤"
        else:
            time_period = "late_night"
            time_desc = "새벽"

        # Today's calendar events from local cache
        today_str = now.strftime("%Y-%m-%d")
        events = []
        try:
            rows = conn.execute(
                """SELECT summary, start_time, end_time, location, description
                   FROM calendar_events
                   WHERE date(start_time) = ? OR date(end_time) = ?
                   ORDER BY start_time""",
                (today_str, today_str),
            ).fetchall()
            events = [dict(r) for r in rows]
        except Exception:
            pass

        # Find current or next upcoming event
        current_event = None
        next_event = None
        now_iso = now.isoformat()
        for ev in events:
            if ev.get("start_time", "") <= now_iso <= ev.get("end_time", ""):
                current_event = ev
                break
            elif ev.get("start_time", "") > now_iso and next_event is None:
                next_event = ev

        # Recent signals sentiment
        signals = get_unconsumed_signals(conn, limit=10)
        mood_signals = []
        for s in signals:
            evidence = s.get("evidence", "")
            direction = s.get("direction", 0)
            mood_signals.append({
                "evidence": evidence[:100],
                "direction": direction,
                "dimension": s.get("dimension", ""),
            })

        # Current avatar & reference
        avatar_path = get_avatar(conn)
        ref_row = conn.execute("SELECT reference_path FROM persona_meta WHERE id = 1").fetchone()
        reference_path = ref_row["reference_path"] if ref_row and ref_row["reference_path"] else avatar_path

        return {
            "timestamp": now.isoformat(),
            "time_period": time_period,
            "time_desc": time_desc,
            "hour": hour,
            "today_events": events,
            "current_event": current_event,
            "next_event": next_event,
            "recent_signals": mood_signals,
            "avatar_path": avatar_path,
            "reference_path": reference_path,
        }
    finally:
        if close:
            conn.close()


def build_avatar_prompt(context: dict[str, Any]) -> str:
    """Build an image editing prompt based on the current context."""
    parts = []

    # Base character description for consistency
    parts.append(
        "Same character as the input image (young Korean woman, same face and hair style). "
    )

    # Time-based scene/lighting
    time_scenes = {
        "early_morning": "soft golden morning light, cozy atmosphere",
        "morning": "bright natural daylight, fresh morning mood",
        "lunch": "warm midday sun, relaxed lunchtime vibe",
        "afternoon": "clear afternoon light",
        "evening": "warm sunset golden hour lighting",
        "night": "soft indoor lamp lighting, nighttime atmosphere",
        "late_night": "dim ambient lighting, quiet late night mood",
    }
    scene = time_scenes.get(context["time_period"], "natural lighting")
    parts.append(f"Scene lighting: {scene}. ")

    # Event-based outfit/setting
    current = context.get("current_event")
    upcoming = context.get("next_event")
    event = current or upcoming

    if event:
        summary = event.get("summary", "").lower()
        location = event.get("location", "") or ""

        if any(k in summary for k in ["미팅", "meeting", "교수", "발표", "평가", "패널"]):
            parts.append(
                "Wearing smart business casual outfit (blazer or neat blouse). "
                "Professional but approachable expression. "
                "Office or meeting room setting. "
            )
        elif any(k in summary for k in ["놀이공원", "나들이", "여행", "소풍"]):
            parts.append(
                "Wearing casual outing clothes (light jacket, sneakers). "
                "Cheerful excited expression. "
                "Outdoor leisure setting. "
            )
        elif any(k in summary for k in ["실험", "lab"]):
            parts.append(
                "Wearing lab coat over casual clothes. "
                "Focused but friendly expression. "
                "Laboratory or science building setting. "
            )
        elif any(k in summary for k in ["수업", "강의", "pbl", "코드톡", "통계"]):
            parts.append(
                "Wearing comfortable campus-style clothes (hoodie or cardigan). "
                "Attentive studious expression. "
                "University campus or classroom setting. "
            )
        elif "zoom" in location.lower() or "zoom" in summary:
            parts.append(
                "Wearing neat top suitable for video call. "
                "Friendly professional expression. "
                "Clean desk setup with monitor in background. "
            )
        else:
            parts.append(f"Dressed appropriately for: {event.get('summary', '')}. ")
    else:
        # No event — default by time
        if context["time_period"] in ("night", "late_night"):
            parts.append(
                "Wearing comfortable loungewear or oversized hoodie. "
                "Relaxed cozy expression. "
                "Cozy room with warm lighting. "
            )
        elif context["time_period"] == "early_morning":
            parts.append(
                "Wearing casual morning outfit. "
                "Slightly sleepy but warm smile. "
                "Kitchen or living room with morning light. "
            )
        else:
            parts.append(
                "Wearing casual everyday clothes. "
                "Friendly natural expression. "
            )

    # Mood from recent signals — dimension-aware expressions
    signals = context.get("recent_signals", [])
    if signals:
        # Aggregate by dimension
        dim_mood: dict[str, float] = {}
        for s in signals:
            dim = s.get("dimension") or "general"
            direction = s.get("direction") or 0
            dim_mood[dim] = dim_mood.get(dim, 0) + direction

        mood_parts = []

        # Humor signals → playful vs serious face
        if dim_mood.get("humor", 0) > 0.3:
            mood_parts.append("playful smirk, eyes sparkling with mischief")
        elif dim_mood.get("humor", 0) < -0.3:
            mood_parts.append("calm composed expression, subtle knowing smile")

        # Empathy signals → warm vs neutral
        if dim_mood.get("empathy", 0) > 0.3:
            mood_parts.append("warm caring gaze, gentle soft eyes")
        elif dim_mood.get("empathy", 0) < -0.3:
            mood_parts.append("cool collected demeanor, confident gaze")

        # Creativity signals → inspired vs focused
        if dim_mood.get("creativity", 0) > 0.3:
            mood_parts.append("inspired curious expression, head slightly tilted")
        elif dim_mood.get("creativity", 0) < -0.3:
            mood_parts.append("sharp focused expression, determined eyes")

        # Proactiveness signals → energetic vs relaxed
        if dim_mood.get("proactiveness", 0) > 0.3:
            mood_parts.append("energetic posture, leaning forward slightly")
        elif dim_mood.get("proactiveness", 0) < -0.3:
            mood_parts.append("relaxed laid-back posture, casual lean")

        # Assertiveness signals → confident vs soft
        if dim_mood.get("assertiveness", 0) > 0.3:
            mood_parts.append("confident bold expression, direct eye contact")
        elif dim_mood.get("assertiveness", 0) < -0.3:
            mood_parts.append("gentle approachable expression, soft smile")

        # Formality signals → polished vs casual vibe
        if dim_mood.get("formality", 0) > 0.3:
            mood_parts.append("refined elegant posture")
        elif dim_mood.get("formality", 0) < -0.3:
            mood_parts.append("casual relaxed vibe, natural unposed feel")

        # General positive/negative fallback
        if not mood_parts:
            total = sum(dim_mood.values())
            if total > 0.5:
                mood_parts.append("bright happy mood, warm genuine smile")
            elif total < -0.5:
                mood_parts.append("slightly tired or pensive expression, thoughtful eyes")

        if mood_parts:
            parts.append(", ".join(mood_parts) + ". ")

    parts.append(
        "Match the exact visual style of the input image (photorealistic, anime, illustration, etc). "
        "High quality, soft cinematic lighting. "
        "Keep the character's face and identity exactly the same as the input image."
    )

    return "".join(parts)


def get_avatar_gen_info() -> dict[str, Any]:
    """Convenience function: return context + prompt + avatar path in one call."""
    context = get_current_context()
    prompt = build_avatar_prompt(context)
    return {
        "context_summary": {
            "time": context["time_desc"],
            "current_event": context["current_event"].get("summary") if context["current_event"] else None,
            "next_event": context["next_event"].get("summary") if context["next_event"] else None,
            "signal_count": len(context["recent_signals"]),
        },
        "reference_path": context["reference_path"],
        "avatar_path": context["avatar_path"],
        "prompt": prompt,
    }


if __name__ == "__main__":
    info = get_avatar_gen_info()
    print(json.dumps(info, ensure_ascii=False, indent=2))
