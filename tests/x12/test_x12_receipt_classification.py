from pathlib import Path

import pytest

from scripts.x12.persist_eligibility import (
    cleanup_x12_transactions,
    persist_270,
    run_interop_db_sql,
    sql_literal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-valid.edi"
)


def _set_segment_element(
    payload: str,
    segment_name: str,
    element_index: int,
    value: str,
) -> str:
    """
    Replace one element in the first matching X12 segment.

    element_index follows the normal split representation:

        ISA*00*... -> ISA13 is index 13
        GS*...     -> GS06 is index 6
        ST*...     -> ST02 is index 2

    Leading CR/LF characters are preserved so the resulting
    payload remains readable as a normal EDI fixture.
    """

    segments = payload.split("~")

    for index, raw_segment in enumerate(segments):
        prefix_length = len(raw_segment) - len(
            raw_segment.lstrip("\r\n")
        )

        prefix = raw_segment[:prefix_length]
        body = raw_segment[prefix_length:]

        elements = body.split("*")

        if not elements:
            continue

        if elements[0] != segment_name:
            continue

        if len(elements) <= element_index:
            raise AssertionError(
                f"{segment_name} does not contain element "
                f"index {element_index}."
            )

        elements[element_index] = value
        segments[index] = prefix + "*".join(elements)

        return "~".join(segments)

    raise AssertionError(
        f"Segment {segment_name!r} was not found."
    )


def _set_subscriber_member_id(
    payload: str,
    member_id: str,
) -> str:
    """
    Replace NM109 for the subscriber NM1*IL segment.
    """

    segments = payload.split("~")

    for index, raw_segment in enumerate(segments):
        prefix_length = len(raw_segment) - len(
            raw_segment.lstrip("\r\n")
        )

        prefix = raw_segment[:prefix_length]
        body = raw_segment[prefix_length:]

        elements = body.split("*")

        if (
            len(elements) > 9
            and elements[0] == "NM1"
            and elements[1] == "IL"
        ):
            elements[9] = member_id
            segments[index] = prefix + "*".join(elements)

            return "~".join(segments)

    raise AssertionError(
        "Subscriber NM1*IL segment was not found."
    )


def _create_test_270(
    path: Path,
    *,
    isa_control_number: str,
    gs_control_number: str,
    st_control_number: str,
    trace_number: str,
    member_id: str = "MEMBER1001",
) -> Path:
    """
    Create a deterministic valid 270 derived from the canonical
    fixture while assigning a test-specific logical identity.
    """

    payload = VALID_270.read_text(
        encoding="utf-8"
    )

    payload = _set_segment_element(
        payload,
        "ISA",
        13,
        isa_control_number,
    )

    payload = _set_segment_element(
        payload,
        "IEA",
        2,
        isa_control_number,
    )

    payload = _set_segment_element(
        payload,
        "GS",
        6,
        gs_control_number,
    )

    payload = _set_segment_element(
        payload,
        "GE",
        2,
        gs_control_number,
    )

    payload = _set_segment_element(
        payload,
        "ST",
        2,
        st_control_number,
    )

    payload = _set_segment_element(
        payload,
        "SE",
        2,
        st_control_number,
    )

    payload = _set_segment_element(
        payload,
        "TRN",
        2,
        trace_number,
    )

    payload = _set_subscriber_member_id(
        payload,
        member_id,
    )

    path.write_text(
        payload,
        encoding="utf-8",
    )

    return path


def _transaction_ids_for_trace(
    trace_number: str,
) -> list[int]:
    """
    Return canonical transaction IDs associated with one
    deterministic Pytest trace number.
    """

    output = run_interop_db_sql(
        f"""
SELECT x12_transaction_id
FROM audit.x12_transactions
WHERE trace_number = {sql_literal(trace_number)}
ORDER BY x12_transaction_id;
""".strip()
    )

    if not output:
        return []

    return [
        int(line.strip())
        for line in output.splitlines()
        if line.strip()
    ]


def _cleanup_test_trace(
    trace_number: str,
) -> None:
    """
    Remove any prior deterministic test state.

    This makes the tests safely repeatable even if a previous
    run was interrupted before its final cleanup.
    """

    transaction_ids = _transaction_ids_for_trace(
        trace_number
    )

    cleanup_x12_transactions(
        transaction_ids
    )


def _load_receipt_state(
    transaction_id: int,
) -> dict[str, object]:
    """
    Retrieve canonical transaction, receipt, and business-state
    evidence for one X12 transaction.
    """

    output = run_interop_db_sql(
        f"""
SELECT
    t.receipt_count,
    (
        SELECT COUNT(*)
        FROM audit.x12_receipts AS r
        WHERE r.x12_transaction_id =
              t.x12_transaction_id
    ) AS receipt_rows,
    (
        SELECT COUNT(*)
        FROM audit.x12_eligibility AS e
        WHERE e.x12_transaction_id =
              t.x12_transaction_id
    ) AS eligibility_rows,
    COALESCE(
        (
            SELECT string_agg(
                r.attempt_outcome,
                ','
                ORDER BY r.x12_receipt_id
            )
            FROM audit.x12_receipts AS r
            WHERE r.x12_transaction_id =
                  t.x12_transaction_id
        ),
        ''
    ) AS receipt_outcomes,
    COALESCE(
        (
            SELECT MAX(e.member_id)
            FROM audit.x12_eligibility AS e
            WHERE e.x12_transaction_id =
                  t.x12_transaction_id
        ),
        ''
    ) AS canonical_member_id
FROM audit.x12_transactions AS t
WHERE t.x12_transaction_id = {transaction_id};
""".strip()
    )

    if not output:
        raise AssertionError(
            "Canonical X12 transaction was not found."
        )

    fields = output.split("|")

    if len(fields) != 5:
        raise AssertionError(
            "Unexpected X12 receipt-state result: "
            f"{output!r}"
        )

    return {
        "receipt_count": int(fields[0]),
        "receipt_rows": int(fields[1]),
        "eligibility_rows": int(fields[2]),
        "receipt_outcomes": fields[3].split(","),
        "canonical_member_id": fields[4],
    }


def test_exact_replay_reuses_canonical_transaction(
    tmp_path: Path,
) -> None:
    """
    An identical retransmission must create operational receipt
    evidence without duplicating canonical business state.
    """

    trace_number = "PYTEST-REPLAY-270-001"

    _cleanup_test_trace(
        trace_number
    )

    test_270 = _create_test_270(
        tmp_path / "270-exact-replay.edi",
        isa_control_number="990000201",
        gs_control_number="9201",
        st_control_number="9201",
        trace_number=trace_number,
        member_id="MEMBER1001",
    )

    try:
        first_id = persist_270(
            test_270
        )

        second_id = persist_270(
            test_270
        )

        assert first_id == second_id

        state = _load_receipt_state(
            first_id
        )

        assert state["receipt_count"] == 2
        assert state["receipt_rows"] == 2
        assert state["eligibility_rows"] == 1

        assert state["receipt_outcomes"] == [
            "FIRST_DELIVERY",
            "EXACT_REPLAY",
        ]

        assert (
            state["canonical_member_id"]
            == "MEMBER1001"
        )

    finally:
        _cleanup_test_trace(
            trace_number
        )


def test_conflicting_reuse_is_preserved_and_rejected(
    tmp_path: Path,
) -> None:
    """
    Reuse of the same logical X12 identity with a different
    payload must preserve the second receipt as evidence,
    reject processing, and leave canonical business state
    unchanged.
    """

    trace_number = "PYTEST-CONFLICT-270-001"

    _cleanup_test_trace(
        trace_number
    )

    original_270 = _create_test_270(
        tmp_path / "270-conflict-original.edi",
        isa_control_number="990000202",
        gs_control_number="9202",
        st_control_number="9202",
        trace_number=trace_number,
        member_id="MEMBER1001",
    )

    conflicting_270 = _create_test_270(
        tmp_path / "270-conflict-reuse.edi",
        isa_control_number="990000202",
        gs_control_number="9202",
        st_control_number="9202",
        trace_number=trace_number,
        member_id="MEMBER9999",
    )

    try:
        canonical_id = persist_270(
            original_270
        )

        with pytest.raises(
            RuntimeError,
            match="conflicting transaction reuse detected",
        ):
            persist_270(
                conflicting_270
            )

        state = _load_receipt_state(
            canonical_id
        )

        assert state["receipt_count"] == 2
        assert state["receipt_rows"] == 2
        assert state["eligibility_rows"] == 1

        assert state["receipt_outcomes"] == [
            "FIRST_DELIVERY",
            "CONFLICTING_REUSE",
        ]

        assert (
            state["canonical_member_id"]
            == "MEMBER1001"
        )

    finally:
        _cleanup_test_trace(
            trace_number
        )