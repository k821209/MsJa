-- ============================================================
-- 004: Documents — AI-generated writings
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    doc_type        TEXT NOT NULL DEFAULT 'note' CHECK (doc_type IN (
                        'note',         -- general notes
                        'draft',        -- email/message drafts
                        'summary',      -- meeting/conversation summaries
                        'report',       -- research reports
                        'letter',       -- formal letters
                        'creative',     -- creative writing
                        'plan',         -- plans and proposals
                        'log'           -- activity/decision logs
                    )),
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                        'draft', 'final', 'archived'
                    )),
    language        TEXT NOT NULL DEFAULT 'ko',
    word_count      INTEGER NOT NULL DEFAULT 0,
    source_interaction_id TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,
    PRIMARY KEY (document_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type, status);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status) WHERE status != 'archived';
CREATE INDEX IF NOT EXISTS idx_documents_time ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_tags_lookup ON document_tags(tag, document_id);

-- Version history for document edits
CREATE TABLE IF NOT EXISTS document_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    version         INTEGER NOT NULL,
    edited_by       TEXT NOT NULL CHECK (edited_by IN ('ai', 'user')),
    change_summary  TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_doc_versions ON document_versions(document_id, version DESC);

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (4, '004_documents');
