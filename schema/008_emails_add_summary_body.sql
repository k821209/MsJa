-- ============================================================
-- 008: Add summary, body, action_type, extracted_event columns to cached_emails
-- ============================================================

ALTER TABLE cached_emails ADD COLUMN summary TEXT;
ALTER TABLE cached_emails ADD COLUMN body TEXT;
ALTER TABLE cached_emails ADD COLUMN action_type TEXT;
ALTER TABLE cached_emails ADD COLUMN extracted_event TEXT;

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (8, '008_emails_add_summary_body');
