CREATE TABLE IF NOT EXISTS audit.orm_orders (
    orm_order_id BIGSERIAL PRIMARY KEY,

    /*
     * Link this imaging order to the one authoritative
     * HL7 logical transaction that produced it.
     *
     * UNIQUE guarantees that one canonical HL7 transaction
     * cannot create duplicate imaging-order business rows.
     */
    transaction_id BIGINT NOT NULL UNIQUE
        REFERENCES audit.interface_transactions(
            transaction_id
        ),

    message_control_id VARCHAR(100) NOT NULL,

    /*
     * Patient / encounter identity.
     */
    patient_identifier VARCHAR(100) NOT NULL,
    assigning_authority VARCHAR(100),
    identifier_type VARCHAR(20),
    visit_number VARCHAR(100),

    /*
     * HL7 order identity.
     */
    order_control VARCHAR(20) NOT NULL,

    placer_order_number VARCHAR(100) NOT NULL,
    filler_order_number VARCHAR(100) NOT NULL,

    /*
     * Lab interface contract:
     *
     * For this controlled radiology workflow, the HL7 filler
     * order identifier is also the accession identifier that
     * will later be reconciled to DICOM AccessionNumber.
     */
    accession_number VARCHAR(100) NOT NULL,

    order_status VARCHAR(20),

    /*
     * Requested imaging procedure.
     */
    procedure_code VARCHAR(100) NOT NULL,
    procedure_text VARCHAR(255),
    procedure_coding_system VARCHAR(50),

    /*
     * Ordering provider.
     */
    ordering_provider_id VARCHAR(100),
    ordering_provider_family VARCHAR(100),
    ordering_provider_given VARCHAR(100),

    /*
     * Preserve the source HL7 TS value exactly as received.
     * Normalized timestamps can be added later if needed.
     */
    order_datetime_raw VARCHAR(32),

    recorded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    /*
     * Enforce our explicit lab interface contract at the
     * database boundary as well as in Python/Mirth validation.
     */
    CONSTRAINT ck_orm_orders_accession_filler_match
        CHECK (
            accession_number = filler_order_number
        )
);


CREATE INDEX IF NOT EXISTS
    idx_orm_orders_patient
ON audit.orm_orders (
    patient_identifier
);


CREATE INDEX IF NOT EXISTS
    idx_orm_orders_accession
ON audit.orm_orders (
    accession_number
);


CREATE INDEX IF NOT EXISTS
    idx_orm_orders_placer_order
ON audit.orm_orders (
    placer_order_number
);


CREATE INDEX IF NOT EXISTS
    idx_orm_orders_filler_order
ON audit.orm_orders (
    filler_order_number
);


CREATE INDEX IF NOT EXISTS
    idx_orm_orders_recorded_at
ON audit.orm_orders (
    recorded_at
);