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


def replace_patient_name_type(
    segments: list[str],
    new_name_type: str,
) -> list[str]:
    updated = segments.copy()

    for index, segment in enumerate(updated):
        if segment.startswith("PID|"):
            fields = segment.split("|")
            name_components = fields[5].split("^")

            while len(name_components) < 7:
                name_components.append("")

            name_components[6] = new_name_type

            fields[5] = "^".join(name_components)
            updated[index] = "|".join(fields)

            return updated

    raise AssertionError("PID segment not found.")


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
        host="localhost",
        port=6661,
        timeout=30.0,
    )

    ack_text = remove_mllp_frame(
        response
    )

    ack_code, ack_control_id = parse_ack(
        ack_text
    )

    assert ack_control_id == message_control_id

    assert ack_code == expected_ack_code, (
        f"Expected {expected_ack_code}, "
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


def get_quarantine_id(
    message_control_id: str,
) -> int:
    output = run_psql(
        f"""
        SELECT quarantine_id
        FROM audit.quarantined_messages
        WHERE message_control_id = '{message_control_id}'
        ORDER BY quarantined_at DESC
        LIMIT 1;
        """
    )

    assert output, (
        "Expected quarantine record not found."
    )

    return int(output)


def get_quarantine_state(
    quarantine_id: int,
) -> dict:
    output = run_psql(
        f"""
        SELECT
            quarantine_status,
            case_reference,
            reviewed_by,
            review_disposition,
            root_cause_category,
            corrective_action,
            replacement_message_control_id,
            reviewed_at IS NOT NULL,
            corrected_at IS NOT NULL,
            replayed_at IS NOT NULL,
            resolved_at IS NOT NULL
        FROM audit.quarantined_messages
        WHERE quarantine_id = {quarantine_id};
        """
    )

    fields = output.split("|")

    assert len(fields) == 11

    return {
        "status": fields[0],
        "case_reference": fields[1],
        "reviewed_by": fields[2],
        "review_disposition": fields[3],
        "root_cause_category": fields[4],
        "corrective_action": fields[5],
        "replacement_message_control_id": fields[6],
        "reviewed_at": fields[7] == "t",
        "corrected_at": fields[8] == "t",
        "replayed_at": fields[9] == "t",
        "resolved_at": fields[10] == "t",
    }


def count_normal_receipts(
    message_control_id: str,
) -> int:
    output = run_psql(
        f"""
        SELECT COUNT(*)
        FROM audit.interface_messages
        WHERE message_control_id = '{message_control_id}';
        """
    )

    return int(output)


def test_quarantined_adt_can_be_corrected_replayed_and_resolved():
    base_segments = load_hl7_fixture(
        HL7_FIXTURE
    )

    # ---------------------------------------------------------
    # 1. CREATE CONTROLLED INVALID TRANSACTION
    # ---------------------------------------------------------

    original_control_id = generate_control_id(
        "LAB-A04-QUAR"
    )

    invalid_segments = replace_message_control_id(
        base_segments,
        original_control_id,
    )

    invalid_segments = replace_patient_name_type(
        invalid_segments,
        "XYZ",
    )

    invalid_ack = send_segments(
        invalid_segments,
        expected_ack_code="AR",
    )

    assert (
        "Patient name type recognized"
        in invalid_ack
    )

    quarantine_id = get_quarantine_id(
        original_control_id
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "QUARANTINED"

    # ---------------------------------------------------------
    # 2. BEGIN HUMAN / OPERATIONAL REVIEW
    # ---------------------------------------------------------

    case_reference = generate_control_id(
        "INTEROP"
    )

    run_psql(
        f"""
        SELECT audit.begin_quarantine_review(
            {quarantine_id},
            '{case_reference}',
            'synthetic-test-analyst'
        );
        """
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "UNDER_REVIEW"
    assert state["case_reference"] == case_reference
    assert state["reviewed_by"] == "synthetic-test-analyst"
    assert state["reviewed_at"] is True

    # ---------------------------------------------------------
    # 3. DOCUMENT CORRECTION DECISION
    # ---------------------------------------------------------

    replacement_control_id = generate_control_id(
        "LAB-A04-CORRECTED"
    )

    run_psql(
        f"""
        SELECT audit.mark_quarantine_corrected(
            {quarantine_id},
            'CORRECT_AND_REPLAY',
            'INVALID_HL7_CODE',
            'Replace unsupported PID-5.7 XYZ with Legal Name code L.',
            '{replacement_control_id}'
        );
        """
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "CORRECTED"
    assert (
        state["review_disposition"]
        == "CORRECT_AND_REPLAY"
    )
    assert (
        state["root_cause_category"]
        == "INVALID_HL7_CODE"
    )
    assert (
        state["replacement_message_control_id"]
        == replacement_control_id
    )
    assert state["corrected_at"] is True

    # ---------------------------------------------------------
    # 4. BUILD CORRECTED REPLACEMENT TRANSACTION
    #
    # The original quarantined payload remains untouched.
    # A new transaction identity is used for the corrected replay.
    # ---------------------------------------------------------

    corrected_segments = replace_message_control_id(
        base_segments,
        replacement_control_id,
    )

    corrected_segments = replace_patient_name_type(
        corrected_segments,
        "L",
    )

    corrected_ack = send_segments(
        corrected_segments,
        expected_ack_code="AA",
    )

    assert "MSA|AA|" in corrected_ack

    # Corrected replacement must enter the normal processing path.
    assert (
        count_normal_receipts(
            replacement_control_id
        )
        == 1
    )

    # Original invalid message must still remain outside
    # the normal processing path.
    assert (
        count_normal_receipts(
            original_control_id
        )
        == 0
    )

    # ---------------------------------------------------------
    # 5. MARK SUCCESSFUL CONTROLLED REPLAY
    # ---------------------------------------------------------

    run_psql(
        f"""
        SELECT audit.mark_quarantine_replayed(
            {quarantine_id}
        );
        """
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "REPLAYED"
    assert state["replayed_at"] is True

    # ---------------------------------------------------------
    # 6. RECONCILE AND RESOLVE
    #
    # In this test, successful normal-path persistence of the
    # replacement transaction is the reconciliation prerequisite.
    # ---------------------------------------------------------

    assert (
        count_normal_receipts(
            replacement_control_id
        )
        == 1
    )

    run_psql(
        f"""
        SELECT audit.resolve_quarantine(
            {quarantine_id},
            'Corrected replacement transaction received AA '
            'and was verified in normal interface persistence.'
        );
        """
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "RESOLVED"
    assert state["resolved_at"] is True