import subprocess
from pathlib import Path
from uuid import uuid4

from scripts.hl7.send_mllp import (
    build_mllp_frame,
    get_message_control_id,
    load_hl7_fixture,
    parse_ack,
    remove_mllp_frame,
    send_mllp_frame,
)


GOOD_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "hl7"
    / "oru"
    / "oru-r01-lab000001.hl7"
)

INTEROP_DB_CONTAINER = "health-it-mirth-lab-interop-db-1"
INTEROP_DB_USER = "interop_app"
INTEROP_DB_NAME = "interop"

MLLP_HOST = "localhost"
MLLP_PORT = 6662


def generate_control_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def replace_message_control_id(
    segments: list[str],
    new_control_id: str,
) -> list[str]:
    updated = segments.copy()

    for index, segment in enumerate(updated):
        if segment.startswith("MSH|"):
            fields = segment.split("|")
            fields[9] = new_control_id
            updated[index] = "|".join(fields)
            return updated

    raise AssertionError("MSH segment not found.")


def replace_observation_value(
    segments: list[str],
    new_value: str,
) -> list[str]:
    updated = segments.copy()

    for index, segment in enumerate(updated):
        if segment.startswith("OBX|"):
            fields = segment.split("|")
            fields[5] = new_value
            updated[index] = "|".join(fields)
            return updated

    raise AssertionError("OBX segment not found.")


def send_segments(
    segments: list[str],
    expected_ack_code: str,
) -> str:
    message_control_id = get_message_control_id(
        segments
    )

    frame = build_mllp_frame(
        segments
    )

    response = send_mllp_frame(
        frame,
        host=MLLP_HOST,
        port=MLLP_PORT,
        timeout=30.0,
    )

    ack_text = remove_mllp_frame(
        response
    )

    ack_code, ack_control_id = parse_ack(
        ack_text
    )

    assert ack_control_id == message_control_id, (
        "ACK correlation failed. "
        f"Expected MSA-2={message_control_id}, "
        f"received {ack_control_id}."
    )

    assert ack_code == expected_ack_code, (
        f"Expected ACK code {expected_ack_code}, "
        f"received {ack_code}.\n\n"
        f"{ack_text}"
    )

    return ack_text


def run_psql(query: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            INTEROP_DB_CONTAINER,
            "psql",
            "-U",
            INTEROP_DB_USER,
            "-d",
            INTEROP_DB_NAME,
            "-A",
            "-t",
            "-F",
            "|",
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "PostgreSQL command failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    return result.stdout.strip()


def count_accepted_oru_messages(
    message_control_id: str,
) -> int:
    output = run_psql(
        f"""
        SELECT COUNT(*)
        FROM audit.oru_messages
        WHERE message_control_id = '{message_control_id}';
        """
    )

    return int(output)


def get_quarantine_row(
    message_control_id: str,
) -> dict:
    output = run_psql(
        f"""
        SELECT
            failure_category,
            failure_reason,
            quarantine_status,
            patient_identifier,
            payload_sha256
        FROM audit.quarantined_messages
        WHERE message_control_id = '{message_control_id}'
        ORDER BY quarantined_at DESC
        LIMIT 1;
        """
    )

    assert output, (
        "Expected quarantine row was not found "
        f"for {message_control_id}."
    )

    fields = output.split("|")

    assert len(fields) == 5

    return {
        "failure_category": fields[0],
        "failure_reason": fields[1],
        "quarantine_status": fields[2],
        "patient_identifier": fields[3],
        "payload_sha256": fields[4],
    }


def get_accepted_oru_row(
    message_control_id: str,
) -> dict:
    output = run_psql(
        f"""
        SELECT
            m.patient_identifier,
            m.placer_order_number,
            m.filler_order_number,
            m.service_code,
            m.processing_status,
            o.observation_code,
            o.observation_value,
            o.units,
            o.abnormal_flag,
            o.result_status
        FROM audit.oru_messages m
        JOIN audit.oru_observations o
            ON o.oru_message_id = m.oru_message_id
        WHERE m.message_control_id = '{message_control_id}'
        ORDER BY m.received_at DESC
        LIMIT 1;
        """
    )

    assert output, (
        "Expected accepted ORU row was not found "
        f"for {message_control_id}."
    )

    fields = output.split("|")

    assert len(fields) == 10

    return {
        "patient_identifier": fields[0],
        "placer_order_number": fields[1],
        "filler_order_number": fields[2],
        "service_code": fields[3],
        "processing_status": fields[4],
        "observation_code": fields[5],
        "observation_value": fields[6],
        "units": fields[7],
        "abnormal_flag": fields[8],
        "result_status": fields[9],
    }


def test_invalid_oru_is_quarantined_without_blocking_subsequent_messages():
    base_segments = load_hl7_fixture(
        GOOD_FIXTURE
    )

    # ---------------------------------------------------------
    # 1. CREATE A CONTROLLED INVALID ORU
    # ---------------------------------------------------------

    bad_control_id = generate_control_id(
        "LAB-ORU-BAD"
    )

    bad_segments = replace_message_control_id(
        base_segments,
        bad_control_id,
    )

    bad_segments = replace_observation_value(
        bad_segments,
        "ABC",
    )

    bad_ack = send_segments(
        bad_segments,
        expected_ack_code="AR",
    )

    assert (
        "Numeric OBX contains numeric value"
        in bad_ack
    )

    # Invalid ORU must NOT enter accepted-result persistence.
    assert (
        count_accepted_oru_messages(
            bad_control_id
        )
        == 0
    )

    # Invalid ORU must be preserved in quarantine.
    quarantine = get_quarantine_row(
        bad_control_id
    )

    assert (
        quarantine["failure_category"]
        == "VALIDATION_ERROR"
    )

    assert (
        quarantine["failure_reason"]
        == "Numeric OBX contains numeric value"
    )

    assert (
        quarantine["quarantine_status"]
        == "QUARANTINED"
    )

    assert (
        quarantine["patient_identifier"]
        == "LAB000001"
    )

    assert len(
        quarantine["payload_sha256"]
    ) == 64

    # ---------------------------------------------------------
    # 2. SEND A SUBSEQUENT VALID ORU
    #
    # This proves the rejected transaction did not block
    # forward progress for later clinical results.
    # ---------------------------------------------------------

    good_control_id = generate_control_id(
        "LAB-ORU-GOOD"
    )

    good_segments = replace_message_control_id(
        base_segments,
        good_control_id,
    )

    good_ack = send_segments(
        good_segments,
        expected_ack_code="AA",
    )

    assert "Message accepted." in good_ack

    # ---------------------------------------------------------
    # 3. VERIFY NORMAL PERSISTENCE OF THE SUBSEQUENT ORU
    # ---------------------------------------------------------

    accepted = get_accepted_oru_row(
        good_control_id
    )

    assert (
        accepted["patient_identifier"]
        == "LAB000001"
    )

    assert (
        accepted["placer_order_number"]
        == "ORD000001"
    )

    assert (
        accepted["filler_order_number"]
        == "LABRPT000001"
    )

    assert (
        accepted["service_code"]
        == "2345-7"
    )

    assert (
        accepted["processing_status"]
        == "ACCEPTED"
    )

    assert (
        accepted["observation_code"]
        == "2345-7"
    )

    assert (
        accepted["observation_value"]
        == "105"
    )

    assert (
        accepted["units"]
        == "mg/dL"
    )

    assert (
        accepted["abnormal_flag"]
        == "H"
    )

    assert (
        accepted["result_status"]
        == "F"
    )