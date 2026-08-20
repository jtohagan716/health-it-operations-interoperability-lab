ALTER TABLE audit.quarantined_messages
    ADD COLUMN IF NOT EXISTS quarantine_status VARCHAR(30)
        NOT NULL DEFAULT 'QUARANTINED',

    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS replayed_at TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS replacement_message_control_id VARCHAR(100),

    ADD COLUMN IF NOT EXISTS resolution_notes TEXT;


ALTER TABLE audit.quarantined_messages
    DROP CONSTRAINT IF EXISTS chk_quarantined_messages_status;


ALTER TABLE audit.quarantined_messages
    ADD CONSTRAINT chk_quarantined_messages_status
    CHECK (
        quarantine_status IN (
            'QUARANTINED',
            'UNDER_REVIEW',
            'CORRECTED',
            'REPLAYED',
            'RESOLVED'
        )
    );


CREATE INDEX IF NOT EXISTS idx_quarantined_messages_status
    ON audit.quarantined_messages (quarantine_status);


CREATE INDEX IF NOT EXISTS idx_quarantined_messages_resolved_at
    ON audit.quarantined_messages (resolved_at);