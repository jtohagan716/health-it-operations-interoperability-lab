CREATE TABLE IF NOT EXISTS audit.interface_transactions (
    transaction_id BIGSERIAL PRIMARY KEY,

    sending_application VARCHAR(100) NOT NULL,
    sending_facility VARCHAR(100) NOT NULL,
    message_control_id VARCHAR(100) NOT NULL,

    canonical_payload_sha256 VARCHAR(64) NOT NULL,

    first_received_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    last_received_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    receipt_count BIGINT NOT NULL
        DEFAULT 1,

    CONSTRAINT uq_interface_transactions_message_identity
        UNIQUE (
            sending_application,
            sending_facility,
            message_control_id
        ),

    CONSTRAINT ck_interface_transactions_sha256_length
        CHECK (
            length(canonical_payload_sha256) = 64
        ),

    CONSTRAINT ck_interface_transactions_receipt_count
        CHECK (
            receipt_count >= 1
        )
);


ALTER TABLE audit.interface_messages
    ADD COLUMN IF NOT EXISTS transaction_id BIGINT;


ALTER TABLE audit.interface_messages
    ADD COLUMN IF NOT EXISTS attempt_outcome VARCHAR(30);


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_interface_messages_transaction'
          AND conrelid = 'audit.interface_messages'::regclass
    ) THEN
        ALTER TABLE audit.interface_messages
            ADD CONSTRAINT fk_interface_messages_transaction
            FOREIGN KEY (transaction_id)
            REFERENCES audit.interface_transactions (
                transaction_id
            );
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    idx_interface_messages_transaction_id
ON audit.interface_messages (
    transaction_id
);


CREATE INDEX IF NOT EXISTS
    idx_interface_messages_attempt_outcome
ON audit.interface_messages (
    attempt_outcome
);
