-- ============================================================
-- 006: Todos — task management for the AI secretary
-- ============================================================

CREATE TABLE IF NOT EXISTS todos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT,
    priority        TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN (
                        'low', 'medium', 'high', 'urgent'
                    )),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                        'pending', 'in_progress', 'done', 'cancelled'
                    )),
    due_date        TEXT,                -- ISO 8601 date or datetime
    calendar_event_id TEXT,              -- links to calendar_events.id
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS todo_tags (
    todo_id         INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,
    PRIMARY KEY (todo_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_due ON todos(due_date) WHERE due_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_todos_calendar ON todos(calendar_event_id) WHERE calendar_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_todo_tags_lookup ON todo_tags(tag, todo_id);

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (6, '006_todos');
