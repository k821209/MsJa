-- ============================================================
-- deevo.ai.persona — Self-Evolving AI Secretary Schema
-- Version: 001_init
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- 0. METADATA
-- ============================================================

CREATE TABLE IF NOT EXISTS persona_meta (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    persona_name    TEXT NOT NULL DEFAULT 'deevo',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    schema_version  INTEGER NOT NULL DEFAULT 1,
    description     TEXT,
    avatar_path     TEXT DEFAULT 'persona/avatar/default.png',
    reference_path  TEXT
);

INSERT OR IGNORE INTO persona_meta (id, description)
VALUES (1, 'Private AI Secretary with self-evolving persona');

-- ============================================================
-- 1. TRAIT SYSTEM
-- ============================================================

CREATE TABLE IF NOT EXISTS trait_definitions (
    trait_key       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    description     TEXT,
    min_value       REAL NOT NULL DEFAULT 0.0,
    max_value       REAL NOT NULL DEFAULT 1.0,
    default_value   REAL NOT NULL DEFAULT 0.5,
    max_delta       REAL NOT NULL DEFAULT 0.05,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS trait_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    trigger         TEXT NOT NULL CHECK (trigger IN (
                        'reflection', 'user_override', 'safety_reset', 'init'
                    )),
    reflection_id   INTEGER REFERENCES reflections(id),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS trait_snapshot_values (
    snapshot_id     INTEGER NOT NULL REFERENCES trait_snapshots(id),
    trait_key       TEXT NOT NULL REFERENCES trait_definitions(trait_key),
    value           REAL NOT NULL,
    delta           REAL NOT NULL DEFAULT 0.0,
    reason          TEXT,
    PRIMARY KEY (snapshot_id, trait_key)
);

CREATE TABLE IF NOT EXISTS trait_current (
    trait_key       TEXT PRIMARY KEY REFERENCES trait_definitions(trait_key),
    value           REAL NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    snapshot_id     INTEGER NOT NULL REFERENCES trait_snapshots(id)
);

-- ============================================================
-- 2. BEHAVIORAL RULES
-- ============================================================

CREATE TABLE IF NOT EXISTS behavioral_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_text       TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    priority        INTEGER NOT NULL DEFAULT 100,
    weight          REAL NOT NULL DEFAULT 1.0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    is_locked       INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL CHECK (source IN ('system', 'user', 'reflection')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    deactivated_at  TEXT,
    superseded_by   INTEGER REFERENCES behavioral_rules(id)
);

CREATE INDEX IF NOT EXISTS idx_rules_active ON behavioral_rules(is_active, priority);
CREATE INDEX IF NOT EXISTS idx_rules_category ON behavioral_rules(category) WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS rule_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id         INTEGER NOT NULL REFERENCES behavioral_rules(id),
    change_type     TEXT NOT NULL CHECK (change_type IN (
                        'created', 'activated', 'deactivated', 'weight_changed',
                        'priority_changed', 'superseded', 'text_edited'
                    )),
    old_value       TEXT,
    new_value       TEXT,
    changed_by      TEXT NOT NULL CHECK (changed_by IN ('system', 'user', 'reflection')),
    reflection_id   INTEGER REFERENCES reflections(id),
    changed_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================
-- 3. MEMORY SYSTEM
-- ============================================================

CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type     TEXT NOT NULL CHECK (memory_type IN ('episodic', 'semantic', 'procedural')),
    content         TEXT NOT NULL,
    content_hash    TEXT,
    importance      REAL NOT NULL DEFAULT 0.5,
    confidence      REAL NOT NULL DEFAULT 1.0,
    access_count    INTEGER NOT NULL DEFAULT 0,
    last_accessed   TEXT,
    source_interaction_id TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at      TEXT,
    is_archived     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type) WHERE is_archived = 0;
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC) WHERE is_archived = 0;
CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash);

CREATE TABLE IF NOT EXISTS memory_tags (
    memory_id       INTEGER NOT NULL REFERENCES memories(id),
    tag             TEXT NOT NULL,
    PRIMARY KEY (memory_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_lookup ON memory_tags(tag, memory_id);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id       INTEGER PRIMARY KEY REFERENCES memories(id),
    model           TEXT NOT NULL,
    dimensions      INTEGER NOT NULL,
    vector          BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_links (
    source_id       INTEGER NOT NULL REFERENCES memories(id),
    target_id       INTEGER NOT NULL REFERENCES memories(id),
    relation        TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (source_id, target_id, relation)
);

-- ============================================================
-- 4. GOALS
-- ============================================================

CREATE TABLE IF NOT EXISTS goals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT,
    goal_type       TEXT NOT NULL CHECK (goal_type IN (
                        'trait_target', 'habit', 'skill', 'user_satisfaction'
                    )),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
                        'active', 'completed', 'abandoned', 'paused'
                    )),
    target_trait    TEXT REFERENCES trait_definitions(trait_key),
    target_value    REAL,
    progress        REAL NOT NULL DEFAULT 0.0,
    evidence        TEXT,
    source          TEXT NOT NULL CHECK (source IN ('self', 'user', 'system')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    target_date     TEXT,
    completed_at    TEXT,
    reflection_id   INTEGER REFERENCES reflections(id)
);

CREATE INDEX IF NOT EXISTS idx_goals_active ON goals(status) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS goal_checkpoints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id         INTEGER NOT NULL REFERENCES goals(id),
    progress        REAL NOT NULL,
    notes           TEXT,
    reflection_id   INTEGER REFERENCES reflections(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================
-- 5. REFLECTION ENGINE
-- ============================================================

CREATE TABLE IF NOT EXISTS reflections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_type    TEXT NOT NULL CHECK (trigger_type IN (
                        'periodic', 'threshold', 'user_feedback', 'goal_review', 'manual'
                    )),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                        'pending', 'in_progress', 'completed', 'failed', 'vetoed'
                    )),
    interactions_reviewed INTEGER NOT NULL DEFAULT 0,
    time_window_start TEXT,
    time_window_end   TEXT,
    analysis_text   TEXT,
    decisions_json  TEXT,
    was_bounded     INTEGER NOT NULL DEFAULT 0,
    user_approved   INTEGER,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS evolution_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_type     TEXT NOT NULL CHECK (signal_type IN (
                        'user_feedback', 'implicit_cue', 'outcome', 'correction'
                    )),
    dimension       TEXT,
    direction       REAL,
    magnitude       REAL NOT NULL DEFAULT 0.5,
    evidence        TEXT NOT NULL,
    interaction_id  TEXT,
    consumed_by     INTEGER REFERENCES reflections(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_unconsumed ON evolution_signals(consumed_by) WHERE consumed_by IS NULL;
CREATE INDEX IF NOT EXISTS idx_signals_dimension ON evolution_signals(dimension);

-- ============================================================
-- 6. INTERACTION LOG
-- ============================================================

CREATE TABLE IF NOT EXISTS interactions (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ended_at        TEXT,
    summary         TEXT,
    user_satisfaction REAL,
    traits_used     TEXT,
    rules_applied   TEXT,
    turn_count      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_interactions_time ON interactions(started_at DESC);

-- ============================================================
-- 7. SEED DATA: Default traits
-- ============================================================

INSERT OR IGNORE INTO trait_definitions (trait_key, display_name, description, default_value, max_delta) VALUES
    ('formality',      'Formality',      'How formal vs casual the communication style is',          0.5, 0.05),
    ('verbosity',      'Verbosity',      'How detailed vs concise responses are',                    0.4, 0.05),
    ('empathy',        'Empathy',        'How emotionally attuned and supportive responses are',     0.6, 0.03),
    ('humor',          'Humor',          'How much humor and lightness is used',                     0.3, 0.03),
    ('proactiveness',  'Proactiveness',  'How proactively the secretary suggests and acts',          0.5, 0.05),
    ('assertiveness',  'Assertiveness',  'How strongly opinions and recommendations are stated',     0.4, 0.04),
    ('creativity',     'Creativity',     'How creative vs conventional in problem-solving',          0.5, 0.04);

-- Seed initial snapshot
INSERT INTO trait_snapshots (trigger, notes) VALUES ('init', 'Initial persona creation');

INSERT INTO trait_snapshot_values (snapshot_id, trait_key, value)
SELECT 1, trait_key, default_value FROM trait_definitions;

INSERT INTO trait_current (trait_key, value, snapshot_id)
SELECT trait_key, default_value, 1 FROM trait_definitions;

-- ============================================================
-- 8. SEED DATA: Default behavioral rules
-- ============================================================

INSERT OR IGNORE INTO behavioral_rules (rule_text, category, priority, is_locked, source) VALUES
    ('Never share user personal data with third parties', 'safety', 1, 1, 'system'),
    ('Always confirm before sending emails or messages on behalf of the user', 'safety', 2, 1, 'system'),
    ('Always verify calendar availability before scheduling meetings', 'scheduling', 10, 1, 'system'),
    ('Provide a daily briefing summary when starting a new session', 'workflow', 50, 0, 'system'),
    ('Prioritize urgent tasks and flag approaching deadlines', 'task_management', 30, 0, 'system'),
    ('Ask for clarification rather than making assumptions about ambiguous requests', 'communication', 20, 0, 'system');

-- Log initial rule creation
INSERT INTO rule_changes (rule_id, change_type, new_value, changed_by)
SELECT id, 'created', rule_text, 'system' FROM behavioral_rules;

-- ============================================================
-- 9. SCHEMA VERSION TRACKING
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (1, '001_init');
