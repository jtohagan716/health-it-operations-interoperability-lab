CREATE OR REPLACE FUNCTION audit.record_interface_receipt (
    p_message_control_id VARCHAR,
    p_message_type VARCHAR,
    p_trigger_event VARCHAR,
    p_patient_identifier VARCHAR,
    p_sending_application VARCHAR,
    p_sending_facility VARCHAR,
    p_payload_sha256 VARCHAR
)
RETURNS TABLE (
    recorded_audit_id BIGINT,
    logical_transaction_id BIGINT,
    classified_outcome VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;

    v_canonical_payload_sha256 VARCHAR(64);

    v_attempt_outcome VARCHAR(30);

    v_audit_id BIGINT;
BEGIN

    /*
     * First, attempt to establish a new logical transaction.
     *
     * PostgreSQL's UNIQUE constraint on:
     *
     *     sending_application
     *     sending_facility
     *     message_control_id
     *
     * is the final authority on transaction uniqueness.
     */

    INSERT INTO audit.interface_transactions (
        sending_application,
        sending_facility,
        message_control_id,
        canonical_payload_sha256
    )
    VALUES (
        p_sending_application,
        p_sending_facility,
        p_message_control_id,
        p_payload_sha256
    )
    ON CONFLICT (
        sending_application,
        sending_facility,
        message_control_id
    )
    DO NOTHING
    RETURNING
        transaction_id,
        canonical_payload_sha256
    INTO
        v_transaction_id,
        v_canonical_payload_sha256;


    /*
     * If INSERT returned a transaction_id, this was the
     * first observed delivery of this logical transaction.
     */

    IF v_transaction_id IS NOT NULL THEN

        v_attempt_outcome := 'FIRST_DELIVERY';

    ELSE

        /*
         * The logical transaction already exists.
         *
         * Lock the existing transaction row while we classify
         * and update its receipt metadata.
         */

        SELECT
            transaction_id,
            canonical_payload_sha256
        INTO
            v_transaction_id,
            v_canonical_payload_sha256
        FROM audit.interface_transactions
        WHERE sending_application = p_sending_application
          AND sending_facility = p_sending_facility
          AND message_control_id = p_message_control_id
        FOR UPDATE;


        /*
         * Same logical identity + same payload
         * means exact retransmission.
         *
         * Same logical identity + different payload
         * means conflicting reuse.
         */

        IF v_canonical_payload_sha256 = p_payload_sha256 THEN

            v_attempt_outcome := 'EXACT_REPLAY';

        ELSE

            v_attempt_outcome := 'CONFLICTING_REUSE';

        END IF;


        /*
         * receipt_count represents every observed receipt
         * claiming this logical transaction identity,
         * including conflicting reuse attempts.
         */

        UPDATE audit.interface_transactions
        SET
            receipt_count = receipt_count + 1,
            last_received_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

    END IF;


    /*
     * Preserve every receipt as audit evidence.
     *
     * Each receipt retains its own incoming payload hash
     * and classification while linking back to the single
     * logical transaction.
     */

    INSERT INTO audit.interface_messages (
        message_control_id,
        message_type,
        trigger_event,
        patient_identifier,
        sending_application,
        sending_facility,
        processing_status,
        payload_sha256,
        transaction_id,
        attempt_outcome
    )
    VALUES (
        p_message_control_id,
        p_message_type,
        p_trigger_event,
        p_patient_identifier,
        p_sending_application,
        p_sending_facility,
        'PERSISTED',
        p_payload_sha256,
        v_transaction_id,
        v_attempt_outcome
    )
    RETURNING audit_id
    INTO v_audit_id;


    /*
     * Return useful classification evidence to the caller.
     */

    RETURN QUERY
    SELECT
        v_audit_id,
        v_transaction_id,
        v_attempt_outcome;

END;
$$;
