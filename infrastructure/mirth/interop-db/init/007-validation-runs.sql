CREATE TABLE IF NOT EXISTS audit.validation_runs (
    validation_run_id BIGSERIAL PRIMARY KEY,

    fhir_lineage_id BIGINT NOT NULL,

    run_type VARCHAR(50) NOT NULL,
    scenario_name VARCHAR(200) NOT NULL,

    synthetic BOOLEAN NOT NULL DEFAULT FALSE,

    overall_status VARCHAR(20),

    started_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ,

    CONSTRAINT fk_validation_run_lineage
        FOREIGN KEY (fhir_lineage_id)
        REFERENCES audit.fhir_resource_lineage (
            fhir_lineage_id
        ),

    CONSTRAINT ck_validation_run_status
        CHECK (
            overall_status IS NULL
            OR overall_status IN (
                'PASS',
                'FAIL',
                'ERROR',
                'SKIP'
            )
        )
);


ALTER TABLE audit.validation_results
    ADD COLUMN IF NOT EXISTS validation_run_id BIGINT;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_validation_result_run'
          AND conrelid = 'audit.validation_results'::regclass
    ) THEN
        ALTER TABLE audit.validation_results
            ADD CONSTRAINT fk_validation_result_run
            FOREIGN KEY (validation_run_id)
            REFERENCES audit.validation_runs (
                validation_run_id
            );
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    idx_validation_runs_lineage
ON audit.validation_runs (
    fhir_lineage_id
);


CREATE INDEX IF NOT EXISTS
    idx_validation_runs_synthetic
ON audit.validation_runs (
    synthetic
);


CREATE INDEX IF NOT EXISTS
    idx_validation_runs_started_at
ON audit.validation_runs (
    started_at
);


CREATE INDEX IF NOT EXISTS
    idx_validation_results_run
ON audit.validation_results (
    validation_run_id
);