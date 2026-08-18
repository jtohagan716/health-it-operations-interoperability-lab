ALTER TABLE audit.interface_messages
    ADD COLUMN IF NOT EXISTS payload_sha256 VARCHAR(64);


CREATE INDEX IF NOT EXISTS
    idx_interface_messages_message_identity
ON audit.interface_messages (
    sending_application,
    sending_facility,
    message_control_id
);