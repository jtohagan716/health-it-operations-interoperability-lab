import re
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


HL7_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "hl7"
    / "adt"
    / "adt-a04-lab000001.hl7"
)

INTEROP_DB_CONTAINER = "health-it-mirth-lab-interop-db-1"
INTEROP_DB_USER = "interop_app"
INTEROP_DB_NAME = "interop"


def generate_control_id(prefix: str) -> str:
    return (
        f"{prefix}-"
        f"{uuid4().hex[:12].upper()}"
    )


def replace_message_control_id(
    segments: list[str],
    new_control_id: str,
) -> list[str]:
    updated_segments = segments.copy()

    for index, segment in enumerate(updated_segments):
        if segment.startswith("MSH|"):
            fields = segment.split("|")

            if len(fields) <= 9:
                raise AssertionError(
                    "MSH segment does not contain MSH-10."
                )

            fields[9] = new_control_id
            updated_segments[index] = "|".join(fields)

            return updated_segments

    raise AssertionError("MSH segment not found.")


def replace_patient_name_type(
    segments: list[str],
    new_name_type: str,
) -> list[str]:
    updated_segments = segments.copy()

    for index, segment in enumerate(updated_segments):
        if segment.startswith("PID|"):
            fields = segment.split("|")

            if len(fields) <= 5:
                raise AssertionError(
                    "PID segment does not contain PID-5."
                )

            name_components = fields[5].split("^")

            while len(name_components) < 7:
                name_components.append("")

            name_components[6] = new_name_type

            fields[5] = "^".join(name_components)
            updated_segments[index] = "|".join(fields)

            return updated_segments

    raise AssertionError("PID segment not found.")


def send_segments(
    segments: list[str],
    expected_ack_code: str,
) -> tuple[str, str]:
    message_control_id = get_message_control_id(
        segments
    )

    frame = build_mllp_frame(segments)

    response = send_mllp_frame(
        frame,
        host="localhost",
        port=6661,
        timeout=30.0,
    )

    ack_text = remove_mllp_frame(response)

    ack_code, ack_control_id = parse_ack(
        ack_text
    )

    assert ack_control_id == message_control_id, (
        "ACK correlation failure: "
        f"expected MSA-2 {message_control_id}, "
        f"received {ack_control_id}"
    )

    assert ack_code == expected_ack_code, (
        f"Expected ACK code {expected_ack_code} "
        f"for message {message_control_id}, "
        f"received {ack_code}.\n\n"
        f"ACK:\n{ack_text}"
    )

    return ack_code, ack_text


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
        "PostgreSQL query failed.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    return result.stdout.strip()


def get_quarantine_record(
    message_control_id: str,
) -> dict:
    query = f"""
        SELECT
            message_control_id,
            failure_category,
            failure_reason,
            quarantine_status,
            payload_sha256
        FROM audit.quarantined_messages
        WHERE message_control_id = '{message_control_id}'
        ORDER BY quarantined_at DESC
        LIMIT 1;
    """

    output = run_psql(query)

    assert output, (
        "Expected quarantined message was not found: "
        f"{message_control_id}"
    )

    fields = output.split("|")

    assert len(fields) == 5, (
        "Unexpected quarantine query result: "
        f"{output}"
    )

    return {
        "message_control_id": fields[0],
        "failure_category": fields[1],
        "failure_reason": fields[2],
        "quarantine_status": fields[3],
        "payload_sha256": fields[4],
    }


def count_normal_audit_rows(
    message_control_id: str,
) -> int:
    query = f"""
        SELECT COUNT(*)
        FROM audit.interface_messages
        WHERE message_control_id = '{message_control_id}';
    """

    output = run_psql(query)

    return int(output)


def test_invalid_adt_is_quarantined_without_blocking_subsequent_messages():
    base_segments = load_hl7_fixture(
        HL7_FIXTURE
    )

    # ---------------------------------------------------------
    # 1. VALID MESSAGE BEFORE THE POISON TRANSACTION
    # ---------------------------------------------------------

    before_control_id = generate_control_id(
        "LAB-A04-BEFORE"
    )

    before_segments = replace_message_control_id(
        base_segments,
        before_control_id,
    )

    before_ack_code, _ = send_segments(
        before_segments,
        expected_ack_code="AA",
    )

    assert before_ack_code == "AA"

    # ---------------------------------------------------------
    # 2. CONTROLLED POISON MESSAGE
    #
    # Only PID-5.7 is made invalid. The remaining message
    # contract is left unchanged.
    # ---------------------------------------------------------

    poison_control_id = generate_control_id(
        "LAB-A04-POISON"
    )

    poison_segments = replace_message_control_id(
        base_segments,
        poison_control_id,
    )

    poison_segments = replace_patient_name_type(
        poison_segments,
        "XYZ",
    )

    poison_ack_code, poison_ack = send_segments(
        poison_segments,
        expected_ack_code="AR",
    )

    assert poison_ack_code == "AR"

    assert (
        "Patient name type recognized"
        in poison_ack
    ), (
        "AR acknowledgment did not identify "
        "the expected validation failure."
    )

    # ---------------------------------------------------------
    # 3. PROVE DURABLE QUARANTINE
    # ---------------------------------------------------------

    quarantine = get_quarantine_record(
        poison_control_id
    )

    assert (
        quarantine["message_control_id"]
        == poison_control_id
    )

    assert (
        quarantine["failure_category"]
        == "VALIDATION_ERROR"
    )

    assert (
        quarantine["failure_reason"]
        == "Patient name type recognized"
    )

    assert (
        quarantine["quarantine_status"]
        == "QUARANTINED"
    )

    assert re.fullmatch(
        r"[0-9a-f]{64}",
        quarantine["payload_sha256"],
    ), (
        "Quarantined payload does not contain "
        "a valid SHA-256 fingerprint."
    )

    # The invalid transaction must not enter the normal
    # transaction/audit persistence path.
    assert (
        count_normal_audit_rows(
            poison_control_id
        )
        == 0
    ), (
        "Validation-rejected message was incorrectly "
        "recorded in the normal interface message path."
    )

    # ---------------------------------------------------------
    # 4. VALID MESSAGE AFTER THE POISON TRANSACTION
    #
    # This is the central forward-progress assertion.
    # ---------------------------------------------------------

    after_control_id = generate_control_id(
        "LAB-A04-AFTER"
    )

    after_segments = replace_message_control_id(
        base_segments,
        after_control_id,
    )

    after_ack_code, _ = send_segments(
        after_segments,
        expected_ack_code="AA",
    )

    assert after_ack_code == "AA"