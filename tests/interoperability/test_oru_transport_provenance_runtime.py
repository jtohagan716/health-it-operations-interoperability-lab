from pathlib import Path

from scripts.hl7.oru_scenario import (
    build_oru_segments,
    load_scenario,
)
from scripts.hl7.run_oru_scenarios import (
    sql_literal,
    wait_for_accepted_observation,
)
from scripts.hl7.scenario_runtime import (
    generate_control_id,
    run_psql,
    send_segments,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCENARIO_PATH = (
    PROJECT_ROOT
    / "fixtures"
    / "hl7"
    / "oru"
    / "scenarios"
    / "normal-glucose-final.json"
)


def conflicting_observation_value(
    segments: list[str],
    value: str,
) -> list[str]:
    changed = segments.copy()

    obx_index = next(
        index
        for index, segment in enumerate(changed)
        if segment.startswith("OBX|")
    )

    fields = changed[obx_index].split("|")
    fields[5] = value
    changed[obx_index] = "|".join(fields)

    return changed


def query_transaction_summary(
    message_control_id: str,
) -> dict[str, str]:
    output = run_psql(
        f"""
        SELECT
            t.transaction_id,
            t.receipt_count,
            t.canonical_payload_sha256,
            (
                SELECT COUNT(*)
                FROM audit.interface_messages AS a
                WHERE a.transaction_id = t.transaction_id
            ),
            (
                SELECT string_agg(
                    a.attempt_outcome,
                    ' -> '
                    ORDER BY a.audit_id
                )
                FROM audit.interface_messages AS a
                WHERE a.transaction_id = t.transaction_id
            ),
            (
                SELECT COUNT(*)
                FROM audit.oru_messages AS m
                WHERE m.transaction_id = t.transaction_id
            ),
            (
                SELECT COUNT(*)
                FROM audit.oru_observations AS o
                JOIN audit.oru_messages AS m
                    ON m.oru_message_id = o.oru_message_id
                WHERE m.transaction_id = t.transaction_id
            ),
            (
                SELECT MIN(o.observation_value)
                FROM audit.oru_observations AS o
                JOIN audit.oru_messages AS m
                    ON m.oru_message_id = o.oru_message_id
                WHERE m.transaction_id = t.transaction_id
            ),
            (
                SELECT MIN(m.provenance_status)
                FROM audit.oru_messages AS m
                WHERE m.transaction_id = t.transaction_id
            ),
            (
                SELECT bool_and(
                    a.audit_id = m.source_audit_id
                    AND a.transaction_id = m.transaction_id
                    AND a.attempt_outcome = 'FIRST_DELIVERY'
                )
                FROM audit.oru_messages AS m
                JOIN audit.interface_messages AS a
                    ON a.audit_id = m.source_audit_id
                   AND a.transaction_id = m.transaction_id
                WHERE m.transaction_id = t.transaction_id
            )
        FROM audit.interface_transactions AS t
        WHERE t.message_control_id = {
            sql_literal(message_control_id)
        };
        """
    )

    fields = output.split("|")

    if len(fields) != 10:
        raise RuntimeError(
            "Unexpected ORU transaction summary row: "
            f"{output}"
        )

    return {
        "transaction_id": fields[0],
        "receipt_count": fields[1],
        "canonical_payload_sha256": fields[2],
        "receipt_attempt_count": fields[3],
        "attempt_sequence": fields[4],
        "semantic_oru_count": fields[5],
        "observation_count": fields[6],
        "persisted_observation_value": fields[7],
        "provenance_status": fields[8],
        "source_is_first_delivery": fields[9],
    }


def query_attempts(
    message_control_id: str,
) -> list[dict[str, str]]:
    output = run_psql(
        f"""
        SELECT
            a.attempt_outcome,
            a.processing_status,
            a.payload_sha256,
            (
                a.payload_sha256 =
                t.canonical_payload_sha256
            )
        FROM audit.interface_messages AS a
        JOIN audit.interface_transactions AS t
            ON t.transaction_id = a.transaction_id
        WHERE t.message_control_id = {
            sql_literal(message_control_id)
        }
        ORDER BY a.audit_id;
        """
    )

    attempts = []

    for row in output.splitlines():
        fields = row.split("|")

        if len(fields) != 4:
            raise RuntimeError(
                "Unexpected ORU receipt-attempt row: "
                f"{row}"
            )

        attempts.append(
            {
                "attempt_outcome": fields[0],
                "processing_status": fields[1],
                "payload_sha256": fields[2],
                "matches_canonical": fields[3],
            }
        )

    return attempts


def test_oru_receipt_provenance_replay_and_conflict_runtime():
    scenario = load_scenario(SCENARIO_PATH)

    control_id = generate_control_id(
        "ORU-PROVENANCE-RUNTIME",
        suffix_length=10,
    )

    original_value = scenario["observation"]["value"]

    conflicting_value = (
        "91" if original_value != "91" else "92"
    )

    original_segments = build_oru_segments(
        scenario,
        message_control_id=control_id,
    )

    first_ack = send_segments(
        original_segments,
        host="localhost",
        port=6662,
    )

    assert first_ack.code == "AA"
    assert first_ack.control_id == control_id

    persisted = wait_for_accepted_observation(
        control_id
    )

    assert persisted["observation_value"] == original_value

    replay_ack = send_segments(
        original_segments,
        host="localhost",
        port=6662,
    )

    assert replay_ack.code == "AA"
    assert replay_ack.control_id == control_id

    conflict_ack = send_segments(
        conflicting_observation_value(
            original_segments,
            conflicting_value,
        ),
        host="localhost",
        port=6662,
    )

    assert conflict_ack.code == "AR"
    assert conflict_ack.control_id == control_id

    summary = query_transaction_summary(
        control_id
    )

    assert summary["receipt_count"] == "3"
    assert summary["receipt_attempt_count"] == "3"
    assert summary["attempt_sequence"] == (
        "FIRST_DELIVERY -> EXACT_REPLAY -> "
        "CONFLICTING_REUSE"
    )
    assert summary["semantic_oru_count"] == "1"
    assert summary["observation_count"] == "1"
    assert (
        summary["persisted_observation_value"]
        == original_value
    )
    assert summary["provenance_status"] == "LINKED"
    assert summary["source_is_first_delivery"] == "t"

    attempts = query_attempts(control_id)

    assert [
        attempt["attempt_outcome"]
        for attempt in attempts
    ] == [
        "FIRST_DELIVERY",
        "EXACT_REPLAY",
        "CONFLICTING_REUSE",
    ]

    assert [
        attempt["processing_status"]
        for attempt in attempts
    ] == [
        "PERSISTED",
        "PERSISTED",
        "REJECTED",
    ]

    assert [
        attempt["matches_canonical"]
        for attempt in attempts
    ] == [
        "t",
        "t",
        "f",
    ]

    assert (
        attempts[0]["payload_sha256"]
        == attempts[1]["payload_sha256"]
        == summary["canonical_payload_sha256"]
    )

    assert (
        attempts[2]["payload_sha256"]
        != summary["canonical_payload_sha256"]
    )
