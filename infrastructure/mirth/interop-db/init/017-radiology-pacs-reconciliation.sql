ALTER TABLE audit.radiology_workflows
    ADD COLUMN IF NOT EXISTS
        orthanc_study_id VARCHAR(100),

    ADD COLUMN IF NOT EXISTS
        pacs_reconciliation_status VARCHAR(30)
        NOT NULL
        DEFAULT 'PENDING',

    ADD COLUMN IF NOT EXISTS
        pacs_reconciled_at TIMESTAMPTZ;


ALTER TABLE audit.radiology_workflows
    DROP CONSTRAINT IF EXISTS
        ck_radiology_pacs_reconciliation_status;


ALTER TABLE audit.radiology_workflows
    ADD CONSTRAINT
        ck_radiology_pacs_reconciliation_status
    CHECK (
        pacs_reconciliation_status IN (
            'PENDING',
            'RECONCILED',
            'FAILED'
        )
    );


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_pacs_status
ON audit.radiology_workflows (
    pacs_reconciliation_status
);


CREATE INDEX IF NOT EXISTS
    idx_radiology_workflows_orthanc_study
ON audit.radiology_workflows (
    orthanc_study_id
);