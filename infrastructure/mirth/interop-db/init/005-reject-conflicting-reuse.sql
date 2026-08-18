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

    v_processing_status VARCHAR(30);

    v_audit_id BIGINT;
BEGIN

    /*
     * Attempt to establish a new logical transaction.
     *
     * The UNIQUE constraint on sender/facility/MSH-10 remains
     * the authoritative transaction-identity boundary.
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
     * A newly created logical transaction is the first delivery.
     */

    IF v_transaction_id IS NOT NULL THEN

        v_attempt_outcome := 'FIRST_DELIVERY';

    ELSE

        /*
         * The transaction identity already exists.
         *
         * Lock the canonical transaction while classifying and
         * updating its receipt metadata.
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
         * Same identity + same payload = exact replay.
         *
         * Same identity + different payload = integrity conflict.
         */

        IF v_canonical_payload_sha256 = p_payload_sha256 THEN

            v_attempt_outcome := 'EXACT_REPLAY';

        ELSE

            v_attempt_outcome := 'CONFLICTING_REUSE';

        END IF;


        UPDATE audit.interface_transactions
        SET
            receipt_count = receipt_count + 1,
            last_received_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

    END IF;


    /*
     * Classification and business disposition are separate.
     *
     * FIRST_DELIVERY and EXACT_REPLAY remain accepted.
     *
     * CONFLICTING_REUSE is preserved as audit evidence but
     * explicitly rejected from business processing.
     */

    IF v_attempt_outcome = 'CONFLICTING_REUSE' THEN

        v_processing_status := 'REJECTED';

    ELSE

        v_processing_status := 'PERSISTED';

    END IF;


    /*
     * Preserve every observed receipt, including rejected
     * conflicting content.
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
        v_processing_status,
        p_payload_sha256,
        v_transaction_id,
        v_attempt_outcome
    )
    RETURNING audit_id
    INTO v_audit_id;


    RETURN QUERY
    SELECT
        v_audit_id,
        v_transaction_id,
        v_attempt_outcome;

END;
$$;
