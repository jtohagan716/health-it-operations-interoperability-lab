CREATE TABLE IF NOT EXISTS audit.quarantined_messages (
    quarantine_id BIGSERIAL PRIMARY KEY,

    message_control_id VARCHAR(100),
    message_type VARCHAR(20),
    trigger_event VARCHAR(20),

    patient_identifier VARCHAR(100),

    sending_application VARCHAR(100),
    sending_facility VARCHAR(100),

    failure_category VARCHAR(50) NOT NULL,
    failure_reason TEXT NOT NULL,

    payload_text TEXT NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,

    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quarantined_messages_control_id
    ON audit.quarantined_messages (message_control_id);

CREATE INDEX IF NOT EXISTS idx_quarantined_messages_patient_identifier
    ON audit.quarantined_messages (patient_identifier);

CREATE INDEX IF NOT EXISTS idx_quarantined_messages_quarantined_at
    ON audit.quarantined_messages (quarantined_at);