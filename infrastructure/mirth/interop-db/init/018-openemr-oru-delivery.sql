CREATE TABLE IF NOT EXISTS audit.openemr_oru_targets (
    placer_order_number VARCHAR(100) PRIMARY KEY,
    openemr_order_id BIGINT NOT NULL UNIQUE,
    openemr_patient_id BIGINT NOT NULL,
    openemr_encounter_id BIGINT NOT NULL,
    openemr_lab_id BIGINT NOT NULL,
    patient_identifier VARCHAR(100) NOT NULL,
    patient_family_name VARCHAR(100) NOT NULL,
    patient_given_name VARCHAR(100) NOT NULL,
    patient_date_of_birth CHAR(8) NOT NULL,
    patient_administrative_sex VARCHAR(10) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_openemr_target_order_positive CHECK (openemr_order_id > 0),
    CONSTRAINT ck_openemr_target_patient_positive CHECK (openemr_patient_id > 0),
    CONSTRAINT ck_openemr_target_encounter_positive CHECK (openemr_encounter_id > 0),
    CONSTRAINT ck_openemr_target_lab_positive CHECK (openemr_lab_id > 0)
);

CREATE TABLE IF NOT EXISTS audit.openemr_oru_deliveries (
    delivery_id BIGSERIAL PRIMARY KEY,
    oru_message_id BIGINT NOT NULL UNIQUE
        REFERENCES audit.oru_messages(oru_message_id),
    openemr_order_id BIGINT NOT NULL,
    delivery_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    claimed_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    last_error TEXT,
    openemr_control_id VARCHAR(255),
    report_count INTEGER,
    result_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_openemr_delivery_status CHECK (
        delivery_status IN ('PENDING', 'IN_PROGRESS', 'DELIVERED', 'FAILED')
    ),
    CONSTRAINT ck_openemr_delivery_attempts CHECK (attempt_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_openemr_oru_deliveries_status
    ON audit.openemr_oru_deliveries(delivery_status, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_openemr_oru_active_order
    ON audit.openemr_oru_deliveries(openemr_order_id)
    WHERE delivery_status IN ('PENDING', 'IN_PROGRESS', 'DELIVERED');

CREATE OR REPLACE FUNCTION audit.enqueue_openemr_oru_delivery()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_order_id BIGINT;
BEGIN
    IF NEW.processing_status <> 'ACCEPTED' THEN
        RETURN NEW;
    END IF;

    SELECT openemr_order_id
      INTO target_order_id
      FROM audit.openemr_oru_targets
     WHERE placer_order_number = NEW.placer_order_number
       AND active = TRUE;

    IF target_order_id IS NOT NULL THEN
        INSERT INTO audit.openemr_oru_deliveries (
            oru_message_id,
            openemr_order_id
        ) VALUES (
            NEW.oru_message_id,
            target_order_id
        ) ON CONFLICT DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enqueue_openemr_oru_delivery
    ON audit.oru_messages;

CREATE TRIGGER trg_enqueue_openemr_oru_delivery
AFTER INSERT ON audit.oru_messages
FOR EACH ROW
EXECUTE FUNCTION audit.enqueue_openemr_oru_delivery();
