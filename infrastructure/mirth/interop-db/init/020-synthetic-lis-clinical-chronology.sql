BEGIN;

ALTER TABLE lis.orders
    ADD COLUMN IF NOT EXISTS clinical_order_at TIMESTAMPTZ;

DROP FUNCTION IF EXISTS lis.accept_order(
    BIGINT,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    VARCHAR,
    TEXT
);

CREATE OR REPLACE FUNCTION lis.accept_order(
    p_transaction_id BIGINT,
    p_message_control_id VARCHAR,
    p_patient_identifier VARCHAR,
    p_patient_family_name VARCHAR,
    p_patient_given_name VARCHAR,
    p_patient_date_of_birth VARCHAR,
    p_patient_administrative_sex VARCHAR,
    p_visit_number VARCHAR,
    p_placer_order_number VARCHAR,
    p_service_code VARCHAR,
    p_service_text VARCHAR,
    p_service_coding_system VARCHAR,
    p_order_control VARCHAR,
    p_clinical_order_timestamp VARCHAR,
    p_raw_payload TEXT
)
RETURNS TABLE(
    lis_order_id BIGINT,
    filler_order_number VARCHAR,
    created BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_filler VARCHAR(100);
    v_clinical_order_at TIMESTAMPTZ;
BEGIN
    IF p_clinical_order_timestamp !~ '^[0-9]{14}$' THEN
        RAISE EXCEPTION
            'Clinical order timestamp must be YYYYMMDDHHMMSS: %',
            p_clinical_order_timestamp;
    END IF;

    v_clinical_order_at :=
        to_timestamp(
            p_clinical_order_timestamp,
            'YYYYMMDDHH24MISS'
        );

    v_filler := 'SYNLIS-' || p_placer_order_number;

    INSERT INTO lis.orders (
        transaction_id,
        message_control_id,
        patient_identifier,
        patient_family_name,
        patient_given_name,
        patient_date_of_birth,
        patient_administrative_sex,
        visit_number,
        placer_order_number,
        filler_order_number,
        service_code,
        service_text,
        service_coding_system,
        order_control,
        clinical_order_at,
        raw_payload
    )
    VALUES (
        p_transaction_id,
        p_message_control_id,
        p_patient_identifier,
        p_patient_family_name,
        p_patient_given_name,
        p_patient_date_of_birth,
        p_patient_administrative_sex,
        p_visit_number,
        p_placer_order_number,
        v_filler,
        p_service_code,
        p_service_text,
        p_service_coding_system,
        p_order_control,
        v_clinical_order_at,
        p_raw_payload
    )
    ON CONFLICT (transaction_id) DO NOTHING
    RETURNING lis.orders.lis_order_id
    INTO v_id;

    IF v_id IS NOT NULL THEN
        RETURN QUERY
        SELECT v_id, v_filler, TRUE;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        o.lis_order_id,
        o.filler_order_number,
        FALSE
    FROM lis.orders AS o
    WHERE o.transaction_id = p_transaction_id;
END;
$$;

COMMIT;