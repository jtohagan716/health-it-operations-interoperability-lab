CREATE OR REPLACE FUNCTION audit.begin_quarantine_review(
    p_quarantine_id BIGINT,
    p_case_reference VARCHAR,
    p_reviewed_by VARCHAR
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE audit.quarantined_messages
    SET
        quarantine_status = 'UNDER_REVIEW',
        reviewed_at = CURRENT_TIMESTAMP,
        case_reference = p_case_reference,
        reviewed_by = p_reviewed_by
    WHERE quarantine_id = p_quarantine_id
      AND quarantine_status = 'QUARANTINED';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Quarantine % is not in QUARANTINED state',
            p_quarantine_id;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION audit.mark_quarantine_corrected(
    p_quarantine_id BIGINT,
    p_review_disposition VARCHAR,
    p_root_cause_category VARCHAR,
    p_corrective_action TEXT,
    p_replacement_message_control_id VARCHAR
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE audit.quarantined_messages
    SET
        quarantine_status = 'CORRECTED',
        corrected_at = CURRENT_TIMESTAMP,
        review_disposition = p_review_disposition,
        root_cause_category = p_root_cause_category,
        corrective_action = p_corrective_action,
        replacement_message_control_id =
            p_replacement_message_control_id
    WHERE quarantine_id = p_quarantine_id
      AND quarantine_status = 'UNDER_REVIEW';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Quarantine % is not in UNDER_REVIEW state',
            p_quarantine_id;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION audit.mark_quarantine_replayed(
    p_quarantine_id BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE audit.quarantined_messages
    SET
        quarantine_status = 'REPLAYED',
        replayed_at = CURRENT_TIMESTAMP
    WHERE quarantine_id = p_quarantine_id
      AND quarantine_status = 'CORRECTED';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Quarantine % is not in CORRECTED state',
            p_quarantine_id;
    END IF;
END;
$$;


CREATE OR REPLACE FUNCTION audit.resolve_quarantine(
    p_quarantine_id BIGINT,
    p_resolution_notes TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE audit.quarantined_messages
    SET
        quarantine_status = 'RESOLVED',
        resolved_at = CURRENT_TIMESTAMP,
        resolution_notes = p_resolution_notes
    WHERE quarantine_id = p_quarantine_id
      AND quarantine_status = 'REPLAYED';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Quarantine % is not in REPLAYED state',
            p_quarantine_id;
    END IF;
END;
$$;