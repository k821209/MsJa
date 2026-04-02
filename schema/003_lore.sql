-- ============================================================
-- 003: Persona lore — self-narrative entries that evolve
-- ============================================================

CREATE TABLE IF NOT EXISTS persona_lore (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content         TEXT NOT NULL,              -- the lore statement
    significance    REAL NOT NULL DEFAULT 0.5,  -- 0.0-1.0, how central to identity
    category        TEXT NOT NULL DEFAULT 'identity',  -- identity, philosophy, behavior, aesthetic
    is_active       INTEGER NOT NULL DEFAULT 1,
    source          TEXT NOT NULL CHECK (source IN ('seed', 'user', 'reflection')),
    parent_id       INTEGER REFERENCES persona_lore(id),  -- evolved from which lore
    reflection_id   INTEGER REFERENCES reflections(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    archived_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_lore_active ON persona_lore(is_active, significance DESC)
    WHERE is_active = 1;

-- Audit trail for lore changes
CREATE TABLE IF NOT EXISTS lore_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lore_id         INTEGER NOT NULL REFERENCES persona_lore(id),
    change_type     TEXT NOT NULL CHECK (change_type IN (
                        'created', 'evolved', 'merged', 'archived', 'significance_changed'
                    )),
    old_value       TEXT,
    new_value       TEXT,
    changed_by      TEXT NOT NULL CHECK (changed_by IN ('system', 'user', 'reflection', 'seed')),
    reflection_id   INTEGER REFERENCES reflections(id),
    changed_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (3, '003_lore');
