CREATE TABLE IF NOT EXISTS audit.radiology_workflows (
    radiology_workflow_id BIGSERIAL PRIMARY KEY,

    patient_identifier VARCHAR(100) NOT NULL,

    placer_order_number VARCHAR(100) NOT NULL,

    accession_number VARCHAR(100) NOT NULL,

    procedure_code VARCHAR(100) NOT NULL,
    procedure_text VARCHAR(255) NOT NULL,

    study_instance_uid VARCHAR(255) NOT NULL,
    modality VARCHAR(20) NOT NULL,

    oru_message_control_id VARCHAR(100) NOT NULL,

    report_status VARCHAR(20) NOT NULL,
    impression TEXT NOT NULL,

    lineage_status VARCHAR(30) NOT NULL,

    validated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_radiology_accession
        UNIQUE (accession_number),

    CONSTRAINT uq_radiology_study_uid
        UNIQUE (study_instance_uid),

    CONSTRAINT ck_radiology_lineage_status
        CHECK (
            lineage_status IN (
                'MATCHED',
                'QUARANTINED'
            )
        )
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_patient
ON audit.radiology_workflows (
    patient_identifier
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_placer_order
ON audit.radiology_workflows (
    placer_order_number
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_accession
ON audit.radiology_workflows (
    accession_number
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_study_uid
ON audit.radiology_workflows (
    study_instance_uid
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_oru_control
ON audit.radiology_workflows (
    oru_message_control_id
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_status
ON audit.radiology_workflows (
    lineage_status
);