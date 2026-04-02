-- ============================================================
-- 002: Add personal image/avatar reference to persona
-- ============================================================

-- Store image references for the AI persona
CREATE TABLE IF NOT EXISTS persona_images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    image_type      TEXT NOT NULL CHECK (image_type IN (
                        'avatar',           -- main profile image
                        'expression',       -- emotion-specific variants
                        'scene'             -- situational images
                    )),
    label           TEXT NOT NULL,          -- e.g. 'default', 'happy', 'thinking'
    file_path       TEXT NOT NULL,          -- relative path from project root
    description     TEXT,                   -- what this image represents
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_images_active ON persona_images(image_type, is_active)
    WHERE is_active = 1;

-- Add avatar_path to persona_meta
ALTER TABLE persona_meta ADD COLUMN avatar_path TEXT;

UPDATE persona_meta SET avatar_path = 'persona/avatar/default.png' WHERE id = 1;

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (2, '002_persona_image');
