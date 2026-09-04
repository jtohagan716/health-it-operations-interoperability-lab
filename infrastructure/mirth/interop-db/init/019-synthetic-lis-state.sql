CREATE SCHEMA IF NOT EXISTS lis;

CREATE TABLE IF NOT EXISTS lis.orders (
    lis_order_id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL UNIQUE,
    message_control_id VARCHAR(100) NOT NULL,
    patient_identifier VARCHAR(100) NOT NULL,
    patient_family_name VARCHAR(100) NOT NULL,
    patient_given_name VARCHAR(100) NOT NULL,
    patient_date_of_birth CHAR(8) NOT NULL,
    patient_administrative_sex VARCHAR(10) NOT NULL,
    visit_number VARCHAR(100) NOT NULL,
    placer_order_number VARCHAR(100) NOT NULL UNIQUE,
    filler_order_number VARCHAR(100) NOT NULL UNIQUE,
    service_code VARCHAR(100) NOT NULL,
    service_text VARCHAR(255) NOT NULL,
    service_coding_system VARCHAR(50) NOT NULL,
    order_control VARCHAR(10) NOT NULL,
    order_status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED',
    raw_payload TEXT NOT NULL,
    result_message_control_id VARCHAR(100),
    result_value NUMERIC(12,3),
    result_units VARCHAR(40),
    result_reference_range VARCHAR(100),
    result_abnormal_flag VARCHAR(10),
    result_status VARCHAR(10),
    result_attempt_count INTEGER NOT NULL DEFAULT 0,
    result_ack_code VARCHAR(10),
    result_ack_control_id VARCHAR(100),
    last_error TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result_sent_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_lis_order_control CHECK (order_control IN ('NW', 'XO', 'CA')),
    CONSTRAINT ck_lis_order_status CHECK (
        order_status IN ('RECEIVED', 'IN_PROGRESS', 'RESULT_ACKED', 'FAILED')
    ),
    CONSTRAINT ck_lis_result_attempts CHECK (result_attempt_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_lis_orders_status
    ON lis.orders(order_status, received_at);

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
    p_raw_payload TEXT
)
RETURNS TABLE(lis_order_id BIGINT, filler_order_number VARCHAR, created BOOLEAN)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_filler VARCHAR(100);
BEGIN
    v_filler := 'SYNLIS-' || p_placer_order_number;

    INSERT INTO lis.orders (
        transaction_id, message_control_id, patient_identifier,
        patient_family_name, patient_given_name, patient_date_of_birth,
        patient_administrative_sex,
        visit_number, placer_order_number, filler_order_number,
        service_code, service_text, service_coding_system,
        order_control, raw_payload
    ) VALUES (
        p_transaction_id, p_message_control_id, p_patient_identifier,
        p_patient_family_name, p_patient_given_name, p_patient_date_of_birth,
        p_patient_administrative_sex,
        p_visit_number, p_placer_order_number, v_filler,
        p_service_code, p_service_text, p_service_coding_system,
        p_order_control, p_raw_payload
    )
    ON CONFLICT (transaction_id) DO NOTHING
    RETURNING lis.orders.lis_order_id INTO v_id;

    IF v_id IS NOT NULL THEN
        RETURN QUERY SELECT v_id, v_filler, TRUE;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT o.lis_order_id, o.filler_order_number, FALSE
      FROM lis.orders o
     WHERE o.transaction_id = p_transaction_id;
END;
$$;
