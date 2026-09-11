/*
 * Enforce patient-safe ownership of radiology accession
 * numbers at the normalized ORM persistence boundary.
 *
 * Multiple ORM rows may represent legitimate lifecycle
 * events for one order. They are allowed only when patient,
 * placer order, and procedure identity remain consistent.
 */

CREATE OR REPLACE FUNCTION
    audit.enforce_orm_accession_ownership()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    conflicting_order audit.orm_orders%ROWTYPE;
BEGIN
    /*
     * Preserve exact transaction replay behavior.
     *
     * BEFORE INSERT triggers execute before PostgreSQL
     * evaluates ON CONFLICT. If this transaction already
     * owns a row, allow the INSERT to proceed so the channel's
     * ON CONFLICT (transaction_id) DO NOTHING remains
     * idempotent.
     */
    IF TG_OP = 'INSERT'
       AND EXISTS (
            SELECT 1
            FROM audit.orm_orders
            WHERE transaction_id = NEW.transaction_id
       )
    THEN
        RETURN NEW;
    END IF;

    /*
     * Serialize new ownership claims for this accession.
     * This prevents concurrent transactions from both
     * observing an unclaimed accession.
     */
    PERFORM pg_advisory_xact_lock(
        hashtext(NEW.accession_number)
    );

    SELECT existing.*
    INTO conflicting_order
    FROM audit.orm_orders AS existing
    WHERE existing.accession_number =
          NEW.accession_number
      AND ROW(
            existing.patient_identifier,
            existing.placer_order_number,
            existing.procedure_code
          )
          IS DISTINCT FROM
          ROW(
            NEW.patient_identifier,
            NEW.placer_order_number,
            NEW.procedure_code
          )
    ORDER BY existing.orm_order_id
    LIMIT 1;

    IF FOUND THEN
        RAISE EXCEPTION
            USING
                ERRCODE = '23514',
                MESSAGE = format(
                    'ORM accession ownership conflict: '
                    'accession %L is already owned by '
                    'patient %L, placer order %L, '
                    'procedure %L; attempted patient %L, '
                    'placer order %L, procedure %L',
                    NEW.accession_number,
                    conflicting_order.patient_identifier,
                    conflicting_order.placer_order_number,
                    conflicting_order.procedure_code,
                    NEW.patient_identifier,
                    NEW.placer_order_number,
                    NEW.procedure_code
                );
    END IF;

    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS
    trg_enforce_orm_accession_ownership
ON audit.orm_orders;


CREATE TRIGGER
    trg_enforce_orm_accession_ownership
BEFORE INSERT OR UPDATE OF
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code
ON audit.orm_orders
FOR EACH ROW
EXECUTE FUNCTION
    audit.enforce_orm_accession_ownership();