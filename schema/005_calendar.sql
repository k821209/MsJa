-- ============================================================
-- 005: Calendar events cache — synced from Google Calendar via MCP
-- ============================================================

CREATE TABLE IF NOT EXISTS calendar_events (
    id              TEXT PRIMARY KEY,          -- Google Calendar event ID
    calendar_id     TEXT NOT NULL DEFAULT 'primary',
    summary         TEXT NOT NULL,
    description     TEXT,
    location        TEXT,
    start_time      TEXT NOT NULL,             -- ISO 8601
    end_time        TEXT NOT NULL,
    all_day         INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'confirmed',
    html_link       TEXT,
    attendees_json  TEXT,                      -- JSON array
    response_status TEXT,                      -- my response: accepted/declined/tentative
    synced_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_cal_events_time ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_cal_events_date ON calendar_events(substr(start_time, 1, 10));

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (5, '005_calendar');
