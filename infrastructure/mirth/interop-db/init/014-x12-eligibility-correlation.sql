CREATE TABLE IF NOT EXISTS audit.x12_correlations (
    x12_correlation_id BIGSERIAL PRIMARY KEY,

    request_transaction_id BIGINT NOT NULL,

    response_transaction_id BIGINT NOT NULL,

    correlation_type VARCHAR(30) NOT NULL,

    correlation_status VARCHAR(20) NOT NULL,

    correlated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_x12_correlation_request
        FOREIGN KEY (request_transaction_id)
        REFERENCES audit.x12_transactions (
            x12_transaction_id
        ),

    CONSTRAINT fk_x12_correlation_response
        FOREIGN KEY (response_transaction_id)
        REFERENCES audit.x12_transactions (
            x12_transaction_id
        ),

    CONSTRAINT ck_x12_correlation_type
        CHECK (
            correlation_type IN (
                'ELIGIBILITY'
            )
        ),

    CONSTRAINT ck_x12_correlation_status
        CHECK (
            correlation_status IN (
                'MATCHED'
            )
        ),

    CONSTRAINT ck_x12_correlation_distinct_transactions
        CHECK (
            request_transaction_id
            <> response_transaction_id
        ),

    CONSTRAINT uq_x12_correlation_pair
        UNIQUE (
            request_transaction_id,
            response_transaction_id
        )
);


CREATE INDEX IF NOT EXISTS
    idx_x12_correlations_request
ON audit.x12_correlations (
    request_transaction_id
);


CREATE INDEX IF NOT EXISTS
    idx_x12_correlations_response
ON audit.x12_correlations (
    response_transaction_id
);


CREATE OR REPLACE FUNCTION audit.correlate_x12_eligibility (
    p_request_transaction_id BIGINT,
    p_response_transaction_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_request_type VARCHAR(10);
    v_response_type VARCHAR(10);

    v_request_trace VARCHAR(100);
    v_response_trace VARCHAR(100);

    v_request_member VARCHAR(100);
    v_response_member VARCHAR(100);

    v_request_payer VARCHAR(200);
    v_response_payer VARCHAR(200);

    v_request_provider VARCHAR(200);
    v_response_provider VARCHAR(200);

    v_request_date DATE;
    v_response_date DATE;

    v_request_benefit VARCHAR(20);
    v_response_benefit VARCHAR(20);

    v_correlation_id BIGINT;
BEGIN

    /*
     * Retrieve the X12 transaction types and trace numbers.
     *
     * For this controlled lab workflow:
     *
     *     request  = 270 Eligibility Inquiry
     *     response = 271 Eligibility Response
     */

    SELECT
        transaction_set_code,
        trace_number
    INTO
        v_request_type,
        v_request_trace
    FROM audit.x12_transactions
    WHERE x12_transaction_id =
        p_request_transaction_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'X12 request transaction % does not exist',
            p_request_transaction_id;
    END IF;


    SELECT
        transaction_set_code,
        trace_number
    INTO
        v_response_type,
        v_response_trace
    FROM audit.x12_transactions
    WHERE x12_transaction_id =
        p_response_transaction_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'X12 response transaction % does not exist',
            p_response_transaction_id;
    END IF;


    /*
     * Enforce the expected request/response transaction types.
     */

    IF v_request_type <> '270' THEN
        RAISE EXCEPTION
            'Expected request transaction type 270 but found %',
            v_request_type;
    END IF;


    IF v_response_type <> '271' THEN
        RAISE EXCEPTION
            'Expected response transaction type 271 but found %',
            v_response_type;
    END IF;


    /*
     * Compare the business trace number.
     *
     * The trace helps identify which eligibility response
     * belongs to which eligibility inquiry.
     */

    IF v_request_trace IS DISTINCT FROM v_response_trace THEN
        RAISE EXCEPTION
            '270/271 trace numbers do not match: % <> %',
            v_request_trace,
            v_response_trace;
    END IF;


    /*
     * Retrieve eligibility-specific business data.
     */

    SELECT
        member_id,
        payer_name,
        provider_name,
        eligibility_date,
        benefit_code
    INTO
        v_request_member,
        v_request_payer,
        v_request_provider,
        v_request_date,
        v_request_benefit
    FROM audit.x12_eligibility
    WHERE x12_transaction_id =
        p_request_transaction_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            '270 transaction % has no eligibility record',
            p_request_transaction_id;
    END IF;


    SELECT
        member_id,
        payer_name,
        provider_name,
        eligibility_date,
        benefit_code
    INTO
        v_response_member,
        v_response_payer,
        v_response_provider,
        v_response_date,
        v_response_benefit
    FROM audit.x12_eligibility
    WHERE x12_transaction_id =
        p_response_transaction_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            '271 transaction % has no eligibility record',
            p_response_transaction_id;
    END IF;


    /*
     * Business correlation checks.
     *
     * Both transactions can be individually valid while still
     * belonging to different eligibility conversations.
     */

    IF v_request_member IS DISTINCT FROM v_response_member THEN
        RAISE EXCEPTION
            '270/271 member IDs do not match: % <> %',
            v_request_member,
            v_response_member;
    END IF;


    IF v_request_payer IS DISTINCT FROM v_response_payer THEN
        RAISE EXCEPTION
            '270/271 payer values do not match: % <> %',
            v_request_payer,
            v_response_payer;
    END IF;


    IF v_request_provider IS DISTINCT FROM v_response_provider THEN
        RAISE EXCEPTION
            '270/271 provider values do not match: % <> %',
            v_request_provider,
            v_response_provider;
    END IF;


    IF v_request_date IS DISTINCT FROM v_response_date THEN
        RAISE EXCEPTION
            '270/271 eligibility dates do not match: % <> %',
            v_request_date,
            v_response_date;
    END IF;


    IF v_request_benefit IS DISTINCT FROM v_response_benefit THEN
        RAISE EXCEPTION
            '270/271 benefit codes do not match: % <> %',
            v_request_benefit,
            v_response_benefit;
    END IF;


    /*
     * Persist the validated relationship.
     */

    INSERT INTO audit.x12_correlations (
        request_transaction_id,
        response_transaction_id,
        correlation_type,
        correlation_status
    )
    VALUES (
        p_request_transaction_id,
        p_response_transaction_id,
        'ELIGIBILITY',
        'MATCHED'
    )
    ON CONFLICT (
        request_transaction_id,
        response_transaction_id
    )
    DO UPDATE SET
        correlation_status = 'MATCHED',
        correlated_at = CURRENT_TIMESTAMP
    RETURNING x12_correlation_id
    INTO v_correlation_id;


    /*
     * Both transactions have now progressed from individually
     * validated records to a successfully correlated business
     * conversation.
     */

    UPDATE audit.x12_transactions
    SET processing_status = 'CORRELATED'
    WHERE x12_transaction_id IN (
        p_request_transaction_id,
        p_response_transaction_id
    );


    RETURN v_correlation_id;

END;
$$;