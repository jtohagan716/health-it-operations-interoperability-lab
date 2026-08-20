ALTER TABLE audit.quarantined_messages
    ADD COLUMN IF NOT EXISTS case_reference VARCHAR(100),

    ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(100),

    ADD COLUMN IF NOT EXISTS review_disposition VARCHAR(100),

    ADD COLUMN IF NOT EXISTS root_cause_category VARCHAR(100),

    ADD COLUMN IF NOT EXISTS corrective_action TEXT;


CREATE INDEX IF NOT EXISTS idx_quarantined_messages_case_reference
    ON audit.quarantined_messages (case_reference);


CREATE INDEX IF NOT EXISTS idx_quarantined_messages_root_cause
    ON audit.quarantined_messages (root_cause_category);