-- ============================================================
-- 008: Add summary and body columns to cached_emails
-- ============================================================

ALTER TABLE cached_emails ADD COLUMN summary TEXT;
ALTER TABLE cached_emails ADD COLUMN body TEXT;

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (8, '008_emails_add_summary_body');
