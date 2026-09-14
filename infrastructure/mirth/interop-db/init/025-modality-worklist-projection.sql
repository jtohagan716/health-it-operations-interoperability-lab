BEGIN;
/*
 * Durable ORM-to-DICOM Modality Worklist projection.
 *
 * audit.orm_orders remains the canonical accepted order.
 * This table preserves the additional patient and scheduling
 * fields needed to publish a queryable DICOM MWL item.
 */

CREATE TABLE IF NOT EXISTS
    audit.modality_worklist_items (
        mwl_item_id BIGSERIAL PRIMARY KEY,

        orm_order_id BIGINT NOT NULL UNIQUE
            REFERENCES audit.orm_orders (
                orm_order_id
            )
            ON DELETE CASCADE,

        patient_identifier VARCHAR(100) NOT NULL,
        patient_family_name VARCHAR(100) NOT NULL,
        patient_given_name VARCHAR(100) NOT NULL,
        patient_date_of_birth CHAR(8) NOT NULL,
        patient_administrative_sex CHAR(1) NOT NULL,

        accession_number VARCHAR(100) NOT NULL UNIQUE,
        requested_procedure_id VARCHAR(100) NOT NULL,
        procedure_code VARCHAR(100) NOT NULL,
        procedure_description VARCHAR(255) NOT NULL,

        modality VARCHAR(16) NOT NULL,
        scheduled_station_ae_title VARCHAR(16) NOT NULL,
        scheduled_start_date CHAR(8) NOT NULL,
        scheduled_start_time VARCHAR(16) NOT NULL,
        schedule_source VARCHAR(30) NOT NULL,
        scheduled_procedure_step_id VARCHAR(16) NOT NULL UNIQUE,

        study_instance_uid VARCHAR(64),
        orthanc_worklist_id VARCHAR(64) UNIQUE,

        projection_status VARCHAR(20) NOT NULL
            DEFAULT 'PENDING',

        projection_attempt_count INTEGER NOT NULL
            DEFAULT 0,

                last_error TEXT,

        claimed_at TIMESTAMPTZ,
        published_at TIMESTAMPTZ,

        created_at TIMESTAMPTZ NOT NULL
            DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMPTZ NOT NULL
            DEFAULT CURRENT_TIMESTAMP,

        CONSTRAINT ck_mwl_patient_dob
            CHECK (
                patient_date_of_birth ~ '^[0-9]{8}$'
            ),

        CONSTRAINT ck_mwl_patient_sex
            CHECK (
                patient_administrative_sex
                IN ('M', 'F', 'O', 'U')
            ),

        CONSTRAINT ck_mwl_scheduled_date
            CHECK (
                scheduled_start_date ~ '^[0-9]{8}$'
            ),

        CONSTRAINT ck_mwl_scheduled_time
            CHECK (
                scheduled_start_time ~
                '^[0-9]{6}(\.[0-9]{1,6})?$'
            ),

        CONSTRAINT ck_mwl_station_ae_length
            CHECK (
                length(scheduled_station_ae_title)
                BETWEEN 1 AND 16
            ),

        CONSTRAINT ck_mwl_step_id_length
            CHECK (
                length(scheduled_procedure_step_id)
                BETWEEN 1 AND 16
            ),

        CONSTRAINT ck_mwl_schedule_source
            CHECK (
                schedule_source IN (
                    'ORDER_DATETIME',
                    'EXPLICIT_SCHEDULE'
                )
            ),

        CONSTRAINT ck_mwl_projection_status
            CHECK (
                projection_status IN (
                    'PENDING',
                    'IN_PROGRESS',
                    'PUBLISHED',
                    'FAILED',
                    'CANCELLED'
                )
            ),

        CONSTRAINT ck_mwl_attempt_count
            CHECK (
                projection_attempt_count >= 0
            ),

        CONSTRAINT ck_mwl_claimed_identity
            CHECK (
                projection_status <> 'IN_PROGRESS'
                OR claimed_at IS NOT NULL
            ),

        CONSTRAINT ck_mwl_published_identity
            CHECK (
                projection_status <> 'PUBLISHED'
                OR (
                    study_instance_uid IS NOT NULL
                    AND orthanc_worklist_id IS NOT NULL
                    AND published_at IS NOT NULL
                )
            )
    );


CREATE INDEX IF NOT EXISTS
    idx_mwl_projection_status
ON audit.modality_worklist_items (
    projection_status,
    created_at
);


CREATE INDEX IF NOT EXISTS
    idx_mwl_patient_identifier
ON audit.modality_worklist_items (
    patient_identifier
);


CREATE OR REPLACE FUNCTION
    audit.enforce_mwl_orm_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_order audit.orm_orders%ROWTYPE;
BEGIN
    SELECT orders.*
    INTO parent_order
    FROM audit.orm_orders AS orders
    WHERE orders.orm_order_id =
          NEW.orm_order_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            USING
                ERRCODE = '23503',
                MESSAGE = format(
                    'MWL projection references missing '
                    'ORM order %s',
                    NEW.orm_order_id
                );
    END IF;

    IF ROW(
        NEW.patient_identifier,
        NEW.accession_number,
        NEW.requested_procedure_id,
        NEW.procedure_code
    )
    IS DISTINCT FROM
    ROW(
        parent_order.patient_identifier,
        parent_order.accession_number,
        parent_order.placer_order_number,
        parent_order.procedure_code
    )
    THEN
        RAISE EXCEPTION
            USING
                ERRCODE = '23514',
                MESSAGE = format(
                    'MWL projection identity does not match '
                    'canonical ORM order %s',
                    NEW.orm_order_id
                );
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS
    trg_enforce_mwl_orm_identity
ON audit.modality_worklist_items;


CREATE TRIGGER
    trg_enforce_mwl_orm_identity
BEFORE INSERT OR UPDATE OF
    orm_order_id,
    patient_identifier,
    accession_number,
    requested_procedure_id,
    procedure_code
ON audit.modality_worklist_items
FOR EACH ROW
EXECUTE FUNCTION
    audit.enforce_mwl_orm_identity();
COMMIT;