-- ============================================================
-- 007: Email cache — synced from Gmail via MCP
-- ============================================================

CREATE TABLE IF NOT EXISTS cached_emails (
    message_id      TEXT PRIMARY KEY,
    thread_id       TEXT,
    subject         TEXT,
    sender          TEXT NOT NULL,
    recipients      TEXT,                      -- TO field
    cc              TEXT,
    snippet         TEXT,
    label_ids       TEXT,                      -- JSON array
    category        TEXT DEFAULT 'personal',   -- personal, updates, promotions, social
    is_unread       INTEGER NOT NULL DEFAULT 1,
    is_important    INTEGER NOT NULL DEFAULT 0,
    internal_date   TEXT,                      -- ISO 8601
    size_estimate   INTEGER,
    summary         TEXT,                      -- AI-generated one-line Korean summary
    body            TEXT,                      -- full email body (cached for important emails)
    synced_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_emails_date ON cached_emails(internal_date DESC);
CREATE INDEX IF NOT EXISTS idx_emails_unread ON cached_emails(is_unread) WHERE is_unread = 1;

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (7, '007_emails');
