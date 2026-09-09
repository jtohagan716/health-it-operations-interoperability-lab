BEGIN;

/*
 * Permit a composite foreign key to prove that an individual
 * receipt attempt belongs to the referenced logical transaction.
 *
 * audit_id is already globally unique, but PostgreSQL requires
 * the complete referenced column set to have a unique constraint
 * for a composite foreign key.
 */
ALTER TABLE audit.interface_messages
    ADD CONSTRAINT
        uq_interface_messages_audit_transaction
    UNIQUE (
        audit_id,
        transaction_id
    );


/*
 * Connect the semantic ORU record to:
 *
 * 1. the logical transport transaction; and
 * 2. the exact receipt attempt that produced the semantic record.
 *
 * Existing ORU rows predate this relationship and remain explicitly
 * identified as LEGACY_UNLINKED. Their provenance must not be guessed.
 */
ALTER TABLE audit.oru_messages
    ADD COLUMN transaction_id BIGINT,
    ADD COLUMN source_audit_id BIGINT,
    ADD COLUMN provenance_status VARCHAR(30);


UPDATE audit.oru_messages
SET provenance_status = 'LEGACY_UNLINKED'
WHERE provenance_status IS NULL;


ALTER TABLE audit.oru_messages
    ALTER COLUMN provenance_status
        SET NOT NULL;


ALTER TABLE audit.oru_messages
    ADD CONSTRAINT fk_oru_messages_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES audit.interface_transactions(
            transaction_id
        );


/*
 * This composite relationship is stronger than two independent
 * foreign keys. It proves that source_audit_id is an attempt belonging
 * to the same transaction_id stored on the semantic ORU row.
 */
ALTER TABLE audit.oru_messages
    ADD CONSTRAINT fk_oru_messages_source_receipt
        FOREIGN KEY (
            source_audit_id,
            transaction_id
        )
        REFERENCES audit.interface_messages(
            audit_id,
            transaction_id
        );


ALTER TABLE audit.oru_messages
    ADD CONSTRAINT ck_oru_messages_provenance_status
        CHECK (
            (
                provenance_status = 'LEGACY_UNLINKED'
                AND transaction_id IS NULL
                AND source_audit_id IS NULL
            )
            OR
            (
                provenance_status = 'LINKED'
                AND transaction_id IS NOT NULL
                AND source_audit_id IS NOT NULL
            )
        );


/*
 * One logical transport transaction may produce no more than one
 * canonical semantic ORU message. Repeated physical receipts remain
 * preserved separately in audit.interface_messages.
 */
CREATE UNIQUE INDEX
    uq_oru_messages_transaction
ON audit.oru_messages(transaction_id)
WHERE transaction_id IS NOT NULL;


CREATE INDEX
    idx_oru_messages_source_audit
ON audit.oru_messages(source_audit_id);


COMMENT ON COLUMN audit.oru_messages.transaction_id IS
    'Logical transport transaction that produced this semantic ORU record.';


COMMENT ON COLUMN audit.oru_messages.source_audit_id IS
    'Exact audit.interface_messages receipt attempt used to create this semantic ORU record.';


COMMENT ON COLUMN audit.oru_messages.provenance_status IS
    'LINKED for records with enforced transport provenance; LEGACY_UNLINKED for records created before provenance linkage existed.';


COMMIT;