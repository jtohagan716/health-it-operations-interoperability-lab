ALTER TABLE audit.x12_transactions
    ADD COLUMN IF NOT EXISTS last_received_at TIMESTAMPTZ
        NOT NULL DEFAULT CURRENT_TIMESTAMP;


ALTER TABLE audit.x12_transactions
    ADD COLUMN IF NOT EXISTS receipt_count BIGINT
        NOT NULL DEFAULT 1;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_x12_transaction_receipt_count'
          AND conrelid = 'audit.x12_transactions'::regclass
    ) THEN
        ALTER TABLE audit.x12_transactions
            ADD CONSTRAINT ck_x12_transaction_receipt_count
            CHECK (
                receipt_count >= 1
            );
    END IF;
END
$$;


CREATE TABLE IF NOT EXISTS audit.x12_receipts (
    x12_receipt_id BIGSERIAL PRIMARY KEY,

    x12_transaction_id BIGINT NOT NULL,

    observed_payload_sha256 VARCHAR(64) NOT NULL,

    attempt_outcome VARCHAR(30) NOT NULL,

    received_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_x12_receipt_transaction
        FOREIGN KEY (x12_transaction_id)
        REFERENCES audit.x12_transactions (
            x12_transaction_id
        )
        ON DELETE CASCADE,

    CONSTRAINT ck_x12_receipt_sha256_length
        CHECK (
            length(observed_payload_sha256) = 64
        ),

    CONSTRAINT ck_x12_receipt_outcome
        CHECK (
            attempt_outcome IN (
                'FIRST_DELIVERY',
                'EXACT_REPLAY',
                'CONFLICTING_REUSE'
            )
        )
);


CREATE INDEX IF NOT EXISTS
    idx_x12_receipts_transaction
ON audit.x12_receipts (
    x12_transaction_id
);


CREATE INDEX IF NOT EXISTS
    idx_x12_receipts_outcome
ON audit.x12_receipts (
    attempt_outcome
);


CREATE INDEX IF NOT EXISTS
    idx_x12_receipts_received_at
ON audit.x12_receipts (
    received_at
);


CREATE OR REPLACE FUNCTION audit.record_x12_receipt (
    p_transaction_set_code VARCHAR,
    p_implementation_version VARCHAR,
    p_interchange_control_number VARCHAR,
    p_group_control_number VARCHAR,
    p_transaction_set_control_number VARCHAR,
    p_sender_id VARCHAR,
    p_receiver_id VARCHAR,
    p_trace_number VARCHAR,
    p_payload_sha256 VARCHAR,
    p_direction VARCHAR,
    p_processing_status VARCHAR
)
RETURNS TABLE (
    recorded_x12_transaction_id BIGINT,
    recorded_x12_receipt_id BIGINT,
    classified_outcome VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;

    v_canonical_payload_sha256 VARCHAR(64);

    v_attempt_outcome VARCHAR(30);

    v_receipt_id BIGINT;
BEGIN

    /*
     * Establish the canonical logical X12 transaction.
     *
     * The existing unique constraint on:
     *
     *   sender_id
     *   receiver_id
     *   transaction_set_code
     *   interchange_control_number
     *   group_control_number
     *   transaction_set_control_number
     *
     * is the final authority on logical transaction identity.
     */

    INSERT INTO audit.x12_transactions (
        transaction_set_code,
        implementation_version,
        interchange_control_number,
        group_control_number,
        transaction_set_control_number,
        sender_id,
        receiver_id,
        trace_number,
        payload_sha256,
        direction,
        processing_status,
        last_received_at,
        receipt_count
    )
    VALUES (
        p_transaction_set_code,
        p_implementation_version,
        p_interchange_control_number,
        p_group_control_number,
        p_transaction_set_control_number,
        p_sender_id,
        p_receiver_id,
        p_trace_number,
        p_payload_sha256,
        p_direction,
        p_processing_status,
        CURRENT_TIMESTAMP,
        1
    )
    ON CONFLICT (
        sender_id,
        receiver_id,
        transaction_set_code,
        interchange_control_number,
        group_control_number,
        transaction_set_control_number
    )
    DO NOTHING
    RETURNING
        x12_transaction_id,
        payload_sha256
    INTO
        v_transaction_id,
        v_canonical_payload_sha256;


    /*
     * A newly inserted transaction is the first delivery.
     */

    IF v_transaction_id IS NOT NULL THEN

        v_attempt_outcome := 'FIRST_DELIVERY';

    ELSE

        /*
         * The logical transaction already exists.
         *
         * Lock the canonical row while classifying this
         * additional receipt.
         */

        SELECT
            x12_transaction_id,
            payload_sha256
        INTO
            v_transaction_id,
            v_canonical_payload_sha256
        FROM audit.x12_transactions
        WHERE sender_id = p_sender_id
          AND receiver_id = p_receiver_id
          AND transaction_set_code =
              p_transaction_set_code
          AND interchange_control_number =
              p_interchange_control_number
          AND group_control_number =
              p_group_control_number
          AND transaction_set_control_number =
              p_transaction_set_control_number
        FOR UPDATE;


        /*
         * Same logical identity + same payload:
         *
         *     exact retransmission
         *
         * Same logical identity + different payload:
         *
         *     conflicting reuse of transaction identity
         */

        IF v_canonical_payload_sha256 =
           p_payload_sha256 THEN

            v_attempt_outcome := 'EXACT_REPLAY';

        ELSE

            v_attempt_outcome := 'CONFLICTING_REUSE';

        END IF;


        /*
         * Count every observed receipt, including conflicting
         * reuse attempts.
         */

        UPDATE audit.x12_transactions
        SET
            receipt_count = receipt_count + 1,
            last_received_at = CURRENT_TIMESTAMP
        WHERE x12_transaction_id =
            v_transaction_id;

    END IF;


    /*
     * Preserve every observed delivery as independent
     * audit evidence.
     */

    INSERT INTO audit.x12_receipts (
        x12_transaction_id,
        observed_payload_sha256,
        attempt_outcome
    )
    VALUES (
        v_transaction_id,
        p_payload_sha256,
        v_attempt_outcome
    )
    RETURNING x12_receipt_id
    INTO v_receipt_id;


    RETURN QUERY
    SELECT
        v_transaction_id,
        v_receipt_id,
        v_attempt_outcome;

END;
$$;