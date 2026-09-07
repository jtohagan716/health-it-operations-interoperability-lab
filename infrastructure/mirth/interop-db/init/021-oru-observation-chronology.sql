BEGIN;

ALTER TABLE audit.oru_messages
    ADD COLUMN IF NOT EXISTS observation_at TIMESTAMPTZ;

COMMIT;