import hashlib
import subprocess
from pathlib import Path

from scripts.x12.eligibility_270 import (
    find_segment,
    load_x12,
    parse_270_business_data,
    validate_270_envelopes,
)
from scripts.x12.eligibility_271 import (
    parse_271_business_data,
    validate_271_envelopes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIRTH_ENV = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / ".env"
)

MIRTH_COMPOSE = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "compose.yaml"
)


def load_env_file(
    path: Path,
) -> dict[str, str]:
    """
    Read a simple KEY=VALUE environment file.

    Blank lines and comments are ignored.
    """

    values: dict[str, str] = {}

    for raw_line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        values[
            key.strip()
        ] = value.strip()

    return values


def payload_sha256(
    path: Path,
) -> str:
    """
    Generate a SHA-256 fingerprint for the raw X12 payload.

    The fingerprint allows the database to distinguish an
    identical retransmission from conflicting reuse of an
    existing logical transaction identity.
    """

    payload = path.read_bytes()

    return hashlib.sha256(
        payload
    ).hexdigest()


def sql_literal(
    value: str | None,
) -> str:
    """
    Represent a controlled lab value as a PostgreSQL
    string literal.

    None becomes SQL NULL.
    """

    if value is None:
        return "NULL"

    escaped = value.replace(
        "'",
        "''",
    )

    return f"'{escaped}'"


def run_interop_db_sql(
    sql: str,
) -> str:
    """
    Execute SQL against the PostgreSQL interoperability
    database running in Docker.

    Returns standard output with surrounding whitespace
    removed.
    """

    env_values = load_env_file(
        MIRTH_ENV
    )

    db_user = env_values[
        "INTEROP_DB_USER"
    ]

    db_name = env_values[
        "INTEROP_DB_NAME"
    ]

    command = [
        "docker",
        "compose",
        "--env-file",
        str(MIRTH_ENV),
        "-f",
        str(MIRTH_COMPOSE),
        "exec",
        "-T",
        "interop-db",
        "psql",
        "-U",
        db_user,
        "-d",
        db_name,
        "-t",
        "-A",
        "-c",
        sql,
    ]

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Interop database SQL execution failed:\n"
            f"{result.stderr}"
        )

    return result.stdout.strip()


def extract_x12_envelope_metadata(
    segments: list[list[str]],
) -> dict[str, str]:
    """
    Extract envelope metadata shared across the controlled
    X12 transaction types used by this lab.

    ISA06 = interchange sender identifier
    ISA08 = interchange receiver identifier
    ST03  = implementation version
    """

    isa = find_segment(
        segments,
        "ISA",
    )

    st = find_segment(
        segments,
        "ST",
    )

    sender_id = (
        isa[6].strip()
        if len(isa) > 6
        else ""
    )

    receiver_id = (
        isa[8].strip()
        if len(isa) > 8
        else ""
    )

    implementation_version = (
        st[3]
        if len(st) > 3
        else ""
    )

    if not sender_id:
        raise ValueError(
            "X12 interchange sender identifier is missing."
        )

    if not receiver_id:
        raise ValueError(
            "X12 interchange receiver identifier is missing."
        )

    return {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "implementation_version": implementation_version,
    }


def record_x12_receipt(
    *,
    transaction_set_code: str,
    implementation_version: str,
    interchange_control_number: str,
    group_control_number: str,
    transaction_set_control_number: str,
    sender_id: str,
    receiver_id: str,
    trace_number: str,
    payload_sha256_value: str,
    direction: str,
    processing_status: str,
) -> dict[str, str | int]:
    """
    Ask PostgreSQL to establish or locate the canonical
    logical X12 transaction and classify this delivery.

    Possible outcomes:

        FIRST_DELIVERY
        EXACT_REPLAY
        CONFLICTING_REUSE
    """

    sql = f"""
SELECT
    recorded_x12_transaction_id,
    recorded_x12_receipt_id,
    classified_outcome
FROM audit.record_x12_receipt(
    {sql_literal(transaction_set_code)},
    {sql_literal(implementation_version)},
    {sql_literal(interchange_control_number)},
    {sql_literal(group_control_number)},
    {sql_literal(transaction_set_control_number)},
    {sql_literal(sender_id)},
    {sql_literal(receiver_id)},
    {sql_literal(trace_number)},
    {sql_literal(payload_sha256_value)},
    {sql_literal(direction)},
    {sql_literal(processing_status)}
);
""".strip()

    output = run_interop_db_sql(
        sql
    )

    if not output:
        raise RuntimeError(
            "X12 receipt classification returned no result."
        )

    fields = output.split("|")

    if len(fields) != 3:
        raise RuntimeError(
            "Unexpected X12 receipt-classification result: "
            f"{output!r}"
        )

    transaction_id_text = fields[0].strip()
    receipt_id_text = fields[1].strip()
    outcome = fields[2].strip()

    if outcome not in {
        "FIRST_DELIVERY",
        "EXACT_REPLAY",
        "CONFLICTING_REUSE",
    }:
        raise RuntimeError(
            "Unexpected X12 receipt outcome: "
            f"{outcome!r}"
        )

    return {
        "x12_transaction_id": int(
            transaction_id_text
        ),
        "x12_receipt_id": int(
            receipt_id_text
        ),
        "outcome": outcome,
    }


def persist_eligibility_business_record(
    *,
    x12_transaction_id: int,
    member_id: str,
    payer_name: str,
    provider_name: str,
    eligibility_date: str,
    benefit_code: str,
    eligibility_status: str | None,
) -> None:
    """
    Persist eligibility-specific business data for a newly
    established canonical X12 transaction.

    Exact replays and conflicting reuse attempts do not
    create additional eligibility rows.
    """

    sql = f"""
INSERT INTO audit.x12_eligibility (
    x12_transaction_id,
    member_id,
    payer_name,
    provider_name,
    eligibility_date,
    benefit_code,
    eligibility_status
)
VALUES (
    {x12_transaction_id},
    {sql_literal(member_id)},
    {sql_literal(payer_name)},
    {sql_literal(provider_name)},
    TO_DATE(
        {sql_literal(eligibility_date)},
        'YYYYMMDD'
    ),
    {sql_literal(benefit_code)},
    {sql_literal(eligibility_status)}
);
""".strip()

    run_interop_db_sql(
        sql
    )


def persist_270(
    path: Path,
) -> int:
    """
    Validate and persist one synthetic X12 270 Eligibility
    Inquiry.

    Receipt behavior:

        FIRST_DELIVERY
            Establish canonical transaction and business row.

        EXACT_REPLAY
            Preserve another receipt but reuse the canonical
            transaction and existing business row.

        CONFLICTING_REUSE
            Preserve the receipt as audit evidence but reject
            the attempt as unsafe logical-identity reuse.

    Returns the canonical x12_transaction_id.
    """

    segments = load_x12(
        path
    )

    envelope = validate_270_envelopes(
        segments
    )

    business = parse_270_business_data(
        segments
    )

    metadata = extract_x12_envelope_metadata(
        segments
    )

    digest = payload_sha256(
        path
    )

    receipt = record_x12_receipt(
        transaction_set_code="270",
        implementation_version=metadata[
            "implementation_version"
        ],
        interchange_control_number=envelope[
            "isa_control_number"
        ],
        group_control_number=envelope[
            "gs_control_number"
        ],
        transaction_set_control_number=envelope[
            "st_control_number"
        ],
        sender_id=metadata[
            "sender_id"
        ],
        receiver_id=metadata[
            "receiver_id"
        ],
        trace_number=business[
            "trace_number"
        ],
        payload_sha256_value=digest,
        direction="OUTBOUND",
        processing_status="VALIDATED",
    )

    transaction_id = int(
        receipt["x12_transaction_id"]
    )

    outcome = str(
        receipt["outcome"]
    )

    if outcome == "FIRST_DELIVERY":
        persist_eligibility_business_record(
            x12_transaction_id=transaction_id,
            member_id=business[
                "member_id"
            ],
            payer_name=business[
                "payer_name"
            ],
            provider_name=business[
                "provider_name"
            ],
            eligibility_date=business[
                "eligibility_date"
            ],
            benefit_code=business[
                "benefit_code"
            ],
            eligibility_status=None,
        )

    elif outcome == "CONFLICTING_REUSE":
        raise RuntimeError(
            "X12 270 conflicting transaction reuse detected: "
            "the logical transaction identity already exists "
            "with a different payload."
        )

    return transaction_id


def persist_271(
    path: Path,
) -> int:
    """
    Validate and persist one synthetic X12 271 Eligibility
    Response.

    Receipt behavior mirrors the 270 processing path.

    Returns the canonical x12_transaction_id.
    """

    segments = load_x12(
        path
    )

    envelope = validate_271_envelopes(
        segments
    )

    business = parse_271_business_data(
        segments
    )

    metadata = extract_x12_envelope_metadata(
        segments
    )

    digest = payload_sha256(
        path
    )

    receipt = record_x12_receipt(
        transaction_set_code="271",
        implementation_version=metadata[
            "implementation_version"
        ],
        interchange_control_number=envelope[
            "isa_control_number"
        ],
        group_control_number=envelope[
            "gs_control_number"
        ],
        transaction_set_control_number=envelope[
            "st_control_number"
        ],
        sender_id=metadata[
            "sender_id"
        ],
        receiver_id=metadata[
            "receiver_id"
        ],
        trace_number=business[
            "trace_number"
        ],
        payload_sha256_value=digest,
        direction="INBOUND",
        processing_status="VALIDATED",
    )

    transaction_id = int(
        receipt["x12_transaction_id"]
    )

    outcome = str(
        receipt["outcome"]
    )

    if outcome == "FIRST_DELIVERY":
        persist_eligibility_business_record(
            x12_transaction_id=transaction_id,
            member_id=business[
                "member_id"
            ],
            payer_name=business[
                "payer_name"
            ],
            provider_name=business[
                "provider_name"
            ],
            eligibility_date=business[
                "eligibility_date"
            ],
            benefit_code=business[
                "benefit_code"
            ],
            eligibility_status=business[
                "eligibility_status"
            ],
        )

    elif outcome == "CONFLICTING_REUSE":
        raise RuntimeError(
            "X12 271 conflicting transaction reuse detected: "
            "the logical transaction identity already exists "
            "with a different payload."
        )

    return transaction_id


def correlate_eligibility_transactions(
    request_transaction_id: int,
    response_transaction_id: int,
) -> int:
    """
    Ask PostgreSQL to validate and persist the relationship
    between a 270 Eligibility Inquiry and a 271 Eligibility
    Response.

    Returns the generated x12_correlation_id.
    """

    sql = f"""
SELECT audit.correlate_x12_eligibility(
    {request_transaction_id},
    {response_transaction_id}
);
""".strip()

    output = run_interop_db_sql(
        sql
    )

    if not output:
        raise RuntimeError(
            "X12 eligibility correlation did not return "
            "a correlation ID."
        )

    return int(
        output
    )


def cleanup_x12_transactions(
    transaction_ids: list[int],
) -> None:
    """
    Remove synthetic X12 transactions created by automated
    tests.

    Correlations are removed first because they reference
    transaction rows.

    Eligibility and receipt rows are removed automatically
    through ON DELETE CASCADE.
    """

    if not transaction_ids:
        return

    normalized_ids = [
        int(transaction_id)
        for transaction_id in transaction_ids
    ]

    ids = ",".join(
        str(transaction_id)
        for transaction_id in normalized_ids
    )

    sql = f"""
DELETE FROM audit.x12_correlations
WHERE request_transaction_id IN ({ids})
   OR response_transaction_id IN ({ids});

DELETE FROM audit.x12_transactions
WHERE x12_transaction_id IN ({ids});
""".strip()

    run_interop_db_sql(
        sql
    )