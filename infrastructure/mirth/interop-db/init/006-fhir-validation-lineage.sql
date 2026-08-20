CREATE TABLE IF NOT EXISTS audit.fhir_resource_lineage (
    fhir_lineage_id BIGSERIAL PRIMARY KEY,

    transaction_id BIGINT NOT NULL,

    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(200) NOT NULL,

    fhir_version VARCHAR(20),
    profile_url TEXT,
    endpoint TEXT,

    discovered_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_fhir_lineage_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES audit.interface_transactions (
            transaction_id
        ),

    CONSTRAINT uq_fhir_lineage_resource
        UNIQUE (
            transaction_id,
            resource_type,
            resource_id
        )
);


CREATE INDEX IF NOT EXISTS
    idx_fhir_lineage_transaction_id
ON audit.fhir_resource_lineage (
    transaction_id
);


CREATE INDEX IF NOT EXISTS
    idx_fhir_lineage_resource
ON audit.fhir_resource_lineage (
    resource_type,
    resource_id
);


CREATE TABLE IF NOT EXISTS audit.validation_results (
    validation_result_id BIGSERIAL PRIMARY KEY,

    fhir_lineage_id BIGINT NOT NULL,

    validation_category VARCHAR(100) NOT NULL,
    validation_rule VARCHAR(200) NOT NULL,

    source_element VARCHAR(200),
    target_element VARCHAR(200),

    expected_value TEXT,
    actual_value TEXT,

    validation_status VARCHAR(20) NOT NULL,

    failure_domain VARCHAR(100),
    diagnostic_message TEXT,

    duration_ms NUMERIC(12,3),

    validated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_validation_fhir_lineage
        FOREIGN KEY (fhir_lineage_id)
        REFERENCES audit.fhir_resource_lineage (
            fhir_lineage_id
        ),

    CONSTRAINT ck_validation_status
        CHECK (
            validation_status IN (
                'PASS',
                'FAIL',
                'SKIP',
                'ERROR'
            )
        )
);


CREATE INDEX IF NOT EXISTS
    idx_validation_results_lineage
ON audit.validation_results (
    fhir_lineage_id
);


CREATE INDEX IF NOT EXISTS
    idx_validation_results_status
ON audit.validation_results (
    validation_status
);


CREATE INDEX IF NOT EXISTS
    idx_validation_results_rule
ON audit.validation_results (
    validation_rule
);


CREATE INDEX IF NOT EXISTS
    idx_validation_results_validated_at
ON audit.validation_results (
    validated_at
);