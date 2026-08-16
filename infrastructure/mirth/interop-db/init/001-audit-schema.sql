CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.interface_messages (
    audit_id BIGSERIAL PRIMARY KEY,

    message_control_id VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    trigger_event VARCHAR(20) NOT NULL,

    patient_identifier VARCHAR(100),

    sending_application VARCHAR(100),
    sending_facility VARCHAR(100),

    processing_status VARCHAR(30) NOT NULL,
    ack_code VARCHAR(10),

    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_interface_messages_control_id
    ON audit.interface_messages (message_control_id);

CREATE INDEX IF NOT EXISTS idx_interface_messages_patient_identifier
    ON audit.interface_messages (patient_identifier);

CREATE INDEX IF NOT EXISTS idx_interface_messages_received_at
    ON audit.interface_messages (received_at);