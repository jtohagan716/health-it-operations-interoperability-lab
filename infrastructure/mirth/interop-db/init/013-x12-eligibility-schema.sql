CREATE TABLE IF NOT EXISTS audit.x12_transactions (
    x12_transaction_id BIGSERIAL PRIMARY KEY,

    transaction_set_code VARCHAR(10) NOT NULL,

    implementation_version VARCHAR(30),

    interchange_control_number VARCHAR(20) NOT NULL,

    group_control_number VARCHAR(20) NOT NULL,

    transaction_set_control_number VARCHAR(20) NOT NULL,

    sender_id VARCHAR(100),

    receiver_id VARCHAR(100),

    trace_number VARCHAR(100),

    payload_sha256 VARCHAR(64) NOT NULL,

    direction VARCHAR(20) NOT NULL,

    processing_status VARCHAR(30) NOT NULL,

    received_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_x12_transaction_set_code
        CHECK (
            transaction_set_code IN (
                '270',
                '271',
                '837',
                '835'
            )
        ),

    CONSTRAINT ck_x12_direction
        CHECK (
            direction IN (
                'INBOUND',
                'OUTBOUND'
            )
        ),

    CONSTRAINT ck_x12_processing_status
        CHECK (
            processing_status IN (
                'RECEIVED',
                'VALIDATED',
                'REJECTED',
                'CORRELATED'
            )
        ),

    CONSTRAINT ck_x12_payload_sha256_length
        CHECK (
            length(payload_sha256) = 64
        ),

    CONSTRAINT uq_x12_transaction_identity
        UNIQUE (
            sender_id,
            receiver_id,
            transaction_set_code,
            interchange_control_number,
            group_control_number,
            transaction_set_control_number
        )
);


CREATE TABLE IF NOT EXISTS audit.x12_eligibility (
    x12_eligibility_id BIGSERIAL PRIMARY KEY,

    x12_transaction_id BIGINT NOT NULL,

    member_id VARCHAR(100) NOT NULL,

    payer_name VARCHAR(200) NOT NULL,

    provider_name VARCHAR(200) NOT NULL,

    eligibility_date DATE NOT NULL,

    benefit_code VARCHAR(20) NOT NULL,

    eligibility_status VARCHAR(20),

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_x12_eligibility_transaction
        FOREIGN KEY (x12_transaction_id)
        REFERENCES audit.x12_transactions (
            x12_transaction_id
        )
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS
    idx_x12_transactions_transaction_set_code
ON audit.x12_transactions (
    transaction_set_code
);


CREATE INDEX IF NOT EXISTS
    idx_x12_transactions_trace_number
ON audit.x12_transactions (
    trace_number
);


CREATE INDEX IF NOT EXISTS
    idx_x12_transactions_received_at
ON audit.x12_transactions (
    received_at
);


CREATE INDEX IF NOT EXISTS
    idx_x12_eligibility_transaction
ON audit.x12_eligibility (
    x12_transaction_id
);


CREATE INDEX IF NOT EXISTS
    idx_x12_eligibility_member_id
ON audit.x12_eligibility (
    member_id
);


CREATE INDEX IF NOT EXISTS
    idx_x12_eligibility_eligibility_date
ON audit.x12_eligibility (
    eligibility_date
);