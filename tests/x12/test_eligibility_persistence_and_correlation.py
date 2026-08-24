import uuid
from pathlib import Path

import pytest

from scripts.x12.persist_eligibility import (
    cleanup_x12_transactions,
    correlate_eligibility_transactions,
    persist_270,
    persist_271,
    run_interop_db_sql,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-valid.edi"
)

VALID_271 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "271-valid.edi"
)


def replace_segment_element(
    text: str,
    segment_id: str,
    element_index: int,
    new_value: str,
) -> str:
    """
    Replace one element in exactly one X12 segment.

    Examples:
        ISA13 = interchange control number
        GS06  = functional group control number
        ST02  = transaction set control number
        TRN02 = business trace number
    """

    segments = text.split("~")
    matches = 0

    for index, raw_segment in enumerate(segments):
        segment = raw_segment.strip()

        if not segment:
            continue

        fields = segment.split("*")

        if fields[0] != segment_id:
            continue

        if len(fields) <= element_index:
            raise ValueError(
                f"{segment_id} does not contain element "
                f"{element_index}."
            )

        fields[element_index] = new_value
        segments[index] = "*".join(fields)
        matches += 1

    if matches != 1:
        raise ValueError(
            f"Expected exactly one {segment_id} segment "
            f"but found {matches}."
        )

    return "~".join(segments)


def create_unique_eligibility_pair(
    tmp_path: Path,
) -> tuple[Path, Path, str]:
    """
    Create a unique synthetic 270/271 request-response pair.

    Unique X12 control numbers prevent collisions with
    prior database test executions.
    """

    seed = int(
        uuid.uuid4().hex[:8],
        16,
    )

    request_interchange = (
        100_000_000
        + seed % 300_000_000
    )

    response_interchange = request_interchange + 1

    request_group = str(
        100_000
        + seed % 700_000
    )

    response_group = str(
        int(request_group) + 1
    )

    request_transaction_set = str(
        1000
        + seed % 7000
    )

    response_transaction_set = str(
        int(request_transaction_set) + 1
    )

    trace_number = (
        "ELIGREQ"
        + uuid.uuid4().hex[:10].upper()
    )

    request_text = VALID_270.read_text(
        encoding="ascii"
    )

    request_text = replace_segment_element(
        request_text,
        "ISA",
        13,
        f"{request_interchange:09d}",
    )

    request_text = replace_segment_element(
        request_text,
        "IEA",
        2,
        f"{request_interchange:09d}",
    )

    request_text = replace_segment_element(
        request_text,
        "GS",
        6,
        request_group,
    )

    request_text = replace_segment_element(
        request_text,
        "GE",
        2,
        request_group,
    )

    request_text = replace_segment_element(
        request_text,
        "ST",
        2,
        request_transaction_set,
    )

    request_text = replace_segment_element(
        request_text,
        "SE",
        2,
        request_transaction_set,
    )

    request_text = replace_segment_element(
        request_text,
        "TRN",
        2,
        trace_number,
    )

    response_text = VALID_271.read_text(
        encoding="ascii"
    )

    response_text = replace_segment_element(
        response_text,
        "ISA",
        13,
        f"{response_interchange:09d}",
    )

    response_text = replace_segment_element(
        response_text,
        "IEA",
        2,
        f"{response_interchange:09d}",
    )

    response_text = replace_segment_element(
        response_text,
        "GS",
        6,
        response_group,
    )

    response_text = replace_segment_element(
        response_text,
        "GE",
        2,
        response_group,
    )

    response_text = replace_segment_element(
        response_text,
        "ST",
        2,
        response_transaction_set,
    )

    response_text = replace_segment_element(
        response_text,
        "SE",
        2,
        response_transaction_set,
    )

    response_text = replace_segment_element(
        response_text,
        "TRN",
        2,
        trace_number,
    )

    request_path = tmp_path / "270-test.edi"
    response_path = tmp_path / "271-test.edi"

    request_path.write_text(
        request_text,
        encoding="ascii",
    )

    response_path.write_text(
        response_text,
        encoding="ascii",
    )

    return (
        request_path,
        response_path,
        trace_number,
    )


def create_wrong_member_response(
    source_response: Path,
    tmp_path: Path,
) -> Path:
    """
    Create an independently valid 271 response for the
    wrong subscriber.

    Its transaction identity is changed so the failure
    under test is correlation, not duplicate identity.
    """

    text = source_response.read_text(
        encoding="ascii"
    )

    text = text.replace(
        "MEMBER1001",
        "MEMBER9999",
    )

    seed = int(
        uuid.uuid4().hex[:8],
        16,
    )

    interchange = (
        700_000_000
        + seed % 200_000_000
    )

    group = str(
        800_000
        + seed % 100_000
    )

    transaction_set = str(
        8000
        + seed % 1000
    )

    text = replace_segment_element(
        text,
        "ISA",
        13,
        f"{interchange:09d}",
    )

    text = replace_segment_element(
        text,
        "IEA",
        2,
        f"{interchange:09d}",
    )

    text = replace_segment_element(
        text,
        "GS",
        6,
        group,
    )

    text = replace_segment_element(
        text,
        "GE",
        2,
        group,
    )

    text = replace_segment_element(
        text,
        "ST",
        2,
        transaction_set,
    )

    text = replace_segment_element(
        text,
        "SE",
        2,
        transaction_set,
    )

    path = tmp_path / "271-wrong-member-test.edi"

    path.write_text(
        text,
        encoding="ascii",
    )

    return path


def test_eligibility_request_response_persists_and_correlates(
    tmp_path: Path,
):
    transaction_ids: list[int] = []

    try:
        request_path, response_path, trace_number = (
            create_unique_eligibility_pair(
                tmp_path
            )
        )

        request_id = persist_270(
            request_path
        )
        transaction_ids.append(
            request_id
        )

        response_id = persist_271(
            response_path
        )
        transaction_ids.append(
            response_id
        )

        correlation_id = (
            correlate_eligibility_transactions(
                request_id,
                response_id,
            )
        )

        assert correlation_id > 0

        lifecycle = run_interop_db_sql(
            f"""
SELECT
    request.processing_status,
    response.processing_status,
    correlation.correlation_status
FROM audit.x12_correlations correlation
JOIN audit.x12_transactions request
    ON request.x12_transaction_id =
       correlation.request_transaction_id
JOIN audit.x12_transactions response
    ON response.x12_transaction_id =
       correlation.response_transaction_id
WHERE correlation.request_transaction_id =
      {request_id}
  AND correlation.response_transaction_id =
      {response_id};
""".strip()
        )

        assert (
            lifecycle
            == "CORRELATED|CORRELATED|MATCHED"
        )

        traces = run_interop_db_sql(
            f"""
SELECT trace_number
FROM audit.x12_transactions
WHERE x12_transaction_id IN (
    {request_id},
    {response_id}
)
ORDER BY x12_transaction_id;
""".strip()
        )

        assert traces.splitlines() == [
            trace_number,
            trace_number,
        ]

    finally:
        cleanup_x12_transactions(
            transaction_ids
        )


def test_wrong_member_response_remains_uncorrelated(
    tmp_path: Path,
):
    transaction_ids: list[int] = []

    try:
        request_path, response_path, _ = (
            create_unique_eligibility_pair(
                tmp_path
            )
        )

        wrong_response_path = (
            create_wrong_member_response(
                response_path,
                tmp_path,
            )
        )

        request_id = persist_270(
            request_path
        )
        transaction_ids.append(
            request_id
        )

        wrong_response_id = persist_271(
            wrong_response_path
        )
        transaction_ids.append(
            wrong_response_id
        )

        with pytest.raises(
            RuntimeError,
            match="member IDs do not match",
        ):
            correlate_eligibility_transactions(
                request_id,
                wrong_response_id,
            )

        status = run_interop_db_sql(
            f"""
SELECT processing_status
FROM audit.x12_transactions
WHERE x12_transaction_id =
      {wrong_response_id};
""".strip()
        )

        assert status == "VALIDATED"

        correlation_count = run_interop_db_sql(
            f"""
SELECT COUNT(*)
FROM audit.x12_correlations
WHERE request_transaction_id =
      {request_id}
  AND response_transaction_id =
      {wrong_response_id};
""".strip()
        )

        assert correlation_count == "0"

    finally:
        cleanup_x12_transactions(
            transaction_ids
        )