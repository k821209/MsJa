"""Calendar event cache — stores events synced from Google Calendar."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from src.db import transaction


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("attendees_json"):
        d["attendees"] = json.loads(d["attendees_json"])
    else:
        d["attendees"] = []
    return d


def sync_event(
    conn: sqlite3.Connection,
    event_id: str,
    summary: str,
    start_time: str,
    end_time: str,
    calendar_id: str = "primary",
    description: str | None = None,
    location: str | None = None,
    all_day: bool = False,
    status: str = "confirmed",
    html_link: str | None = None,
    attendees: list[dict] | None = None,
    response_status: str | None = None,
) -> None:
    """Insert or update a calendar event in the cache."""
    attendees_json = json.dumps(attendees) if attendees else None
    conn.execute(
        """INSERT INTO calendar_events
           (id, calendar_id, summary, description, location, start_time, end_time,
            all_day, status, html_link, attendees_json, response_status, synced_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
           ON CONFLICT(id) DO UPDATE SET
               summary = excluded.summary,
               description = excluded.description,
               location = excluded.location,
               start_time = excluded.start_time,
               end_time = excluded.end_time,
               all_day = excluded.all_day,
               status = excluded.status,
               html_link = excluded.html_link,
               attendees_json = excluded.attendees_json,
               response_status = excluded.response_status,
               synced_at = excluded.synced_at""",
        (event_id, calendar_id, summary, description, location, start_time, end_time,
         int(all_day), status, html_link, attendees_json, response_status),
    )
    conn.commit()


def sync_events_bulk(conn: sqlite3.Connection, events: list[dict]) -> int:
    """Sync multiple events at once. Returns count synced."""
    count = 0
    with transaction(conn):
        for e in events:
            start = e.get("start", {})
            end = e.get("end", {})
            start_time = start.get("dateTime") or start.get("date", "")
            end_time = end.get("dateTime") or end.get("date", "")
            all_day = "date" in start and "dateTime" not in start

            attendees = e.get("attendees", [])
            my_status = None
            for att in attendees:
                if att.get("self"):
                    my_status = att.get("responseStatus")

            conn.execute(
                """INSERT INTO calendar_events
                   (id, calendar_id, summary, description, location, start_time, end_time,
                    all_day, status, html_link, attendees_json, response_status, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                   ON CONFLICT(id) DO UPDATE SET
                       summary = excluded.summary, description = excluded.description,
                       location = excluded.location, start_time = excluded.start_time,
                       end_time = excluded.end_time, all_day = excluded.all_day,
                       status = excluded.status, html_link = excluded.html_link,
                       attendees_json = excluded.attendees_json,
                       response_status = excluded.response_status,
                       synced_at = excluded.synced_at""",
                (e.get("id", ""), "primary", e.get("summary", "(No title)"),
                 e.get("description"), e.get("location"),
                 start_time, end_time, int(all_day),
                 e.get("status", "confirmed"), e.get("htmlLink"),
                 json.dumps(attendees) if attendees else None, my_status),
            )
            count += 1
    return count


def get_events_for_date(conn: sqlite3.Connection, date: str) -> list[dict[str, Any]]:
    """Get events for a specific date (YYYY-MM-DD)."""
    rows = conn.execute(
        """SELECT * FROM calendar_events
           WHERE substr(start_time, 1, 10) = ? AND status != 'cancelled'
           ORDER BY start_time""",
        (date,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_events_range(
    conn: sqlite3.Connection, start: str, end: str
) -> list[dict[str, Any]]:
    """Get events in a date range (YYYY-MM-DD)."""
    rows = conn.execute(
        """SELECT * FROM calendar_events
           WHERE start_time >= ? AND start_time < ? AND status != 'cancelled'
           ORDER BY start_time""",
        (start, end),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_upcoming_events(conn: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    """Get upcoming events from now."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        """SELECT * FROM calendar_events
           WHERE start_time >= ? AND status != 'cancelled'
           ORDER BY start_time LIMIT ?""",
        (now, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_today_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Get today's events."""
    today = datetime.now().strftime("%Y-%m-%d")
    return get_events_for_date(conn, today)


def get_week_events(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Get this week's events grouped by date."""
    today = datetime.now()
    # Monday of this week
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    start = monday.strftime("%Y-%m-%d")
    end = (sunday + timedelta(days=1)).strftime("%Y-%m-%d")

    events = get_events_range(conn, start, end)

    by_date: dict[str, list[dict]] = {}
    for e in events:
        date = e["start_time"][:10]
        by_date.setdefault(date, []).append(e)

    # Fill empty days
    for i in range(7):
        day = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
        by_date.setdefault(day, [])

    return dict(sorted(by_date.items()))
