from pathlib import Path

from scripts.hl7.scenario_runtime import (
    generate_control_id,
    replace_message_control_id,
    replace_observation_value,
    run_psql,
    send_segments,
)
from scripts.hl7.send_mllp import load_hl7_fixture


GOOD_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "hl7"
    / "oru"
    / "oru-r01-lab000001.hl7"
)

MLLP_HOST = "localhost"
MLLP_PORT = 6662


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
        "Expected quarantine record not found "
        f"for {message_control_id}."
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

    assert len(fields) == 11, (
        f"Unexpected quarantine state row: {output}"
    )

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


def count_accepted_oru(
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


def get_accepted_observation(
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
            o.reference_range,
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
        "Corrected ORU was not found in accepted persistence."
    )

    fields = output.split("|")

    assert len(fields) == 11

    return {
        "patient_identifier": fields[0],
        "placer_order_number": fields[1],
        "filler_order_number": fields[2],
        "service_code": fields[3],
        "processing_status": fields[4],
        "observation_code": fields[5],
        "observation_value": fields[6],
        "units": fields[7],
        "reference_range": fields[8],
        "abnormal_flag": fields[9],
        "result_status": fields[10],
    }


def test_quarantined_oru_can_be_corrected_replayed_and_resolved():
    base_segments = load_hl7_fixture(
        GOOD_FIXTURE
    )

    # ---------------------------------------------------------
    # 1. CREATE CONTROLLED INVALID ORU
    #
    # OBX-2 remains NM but OBX-5 becomes non-numeric.
    # ---------------------------------------------------------

    original_control_id = generate_control_id(
        "LAB-ORU-QUAR"
    )

    invalid_segments = replace_message_control_id(
        base_segments,
        original_control_id,
    )

    invalid_segments = replace_observation_value(
        invalid_segments,
        "ABC",
    )

    invalid_ack = send_segments(
        invalid_segments,
        host=MLLP_HOST,
        port=MLLP_PORT,
    )

    assert invalid_ack.code == "AR"

    assert (
        "Numeric OBX contains numeric value"
        in invalid_ack.text
    )

    assert (
        count_accepted_oru(
            original_control_id
        )
        == 0
    )

    quarantine_id = get_quarantine_id(
        original_control_id
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "QUARANTINED"

    # ---------------------------------------------------------
    # 2. BEGIN OPERATIONAL REVIEW
    # ---------------------------------------------------------

    case_reference = generate_control_id(
        "INTEROP"
    )

    run_psql(
        f"""
        SELECT audit.begin_quarantine_review(
            {quarantine_id},
            '{case_reference}',
            'synthetic-lab-interface-analyst'
        );
        """
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "UNDER_REVIEW"
    assert state["case_reference"] == case_reference
    assert (
        state["reviewed_by"]
        == "synthetic-lab-interface-analyst"
    )
    assert state["reviewed_at"] is True

    # ---------------------------------------------------------
    # 3. DOCUMENT CORRECTION DECISION
    #
    # Original quarantined payload remains immutable.
    # We create a replacement transaction with a new MSH-10.
    # ---------------------------------------------------------

    replacement_control_id = generate_control_id(
        "LAB-ORU-CORRECTED"
    )

    run_psql(
        f"""
        SELECT audit.mark_quarantine_corrected(
            {quarantine_id},
            'CORRECT_AND_REPLAY',
            'INVALID_OBSERVATION_VALUE',
            'Replace non-numeric OBX-5 value ABC with validated numeric result 105.',
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
        == "INVALID_OBSERVATION_VALUE"
    )

    assert (
        state["replacement_message_control_id"]
        == replacement_control_id
    )

    assert state["corrected_at"] is True

    # ---------------------------------------------------------
    # 4. CREATE AND SEND CORRECTED REPLACEMENT ORU
    #
    # Start from the known-good clinical result rather than
    # modifying the immutable quarantined payload.
    # ---------------------------------------------------------

    corrected_segments = replace_message_control_id(
        base_segments,
        replacement_control_id,
    )

    corrected_segments = replace_observation_value(
        corrected_segments,
        "105",
    )

    corrected_ack = send_segments(
        corrected_segments,
        host=MLLP_HOST,
        port=MLLP_PORT,
    )

    assert corrected_ack.code == "AA"
    assert "Message accepted." in corrected_ack.text

    # ---------------------------------------------------------
    # 5. VERIFY ACCEPTED CLINICAL RESULT
    # ---------------------------------------------------------

    assert (
        count_accepted_oru(
            replacement_control_id
        )
        == 1
    )

    accepted = get_accepted_observation(
        replacement_control_id
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
        accepted["reference_range"]
        == "70-99"
    )

    assert (
        accepted["abnormal_flag"]
        == "H"
    )

    assert (
        accepted["result_status"]
        == "F"
    )

    assert (
        accepted["processing_status"]
        == "ACCEPTED"
    )

    # Original invalid transaction must remain excluded
    # from accepted ORU persistence.
    assert (
        count_accepted_oru(
            original_control_id
        )
        == 0
    )

    # ---------------------------------------------------------
    # 6. RECORD SUCCESSFUL REPLAY
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
    # 7. RESOLVE AFTER RECONCILIATION
    #
    # Resolution is allowed only after the corrected result
    # has been accepted and its clinical values verified.
    # ---------------------------------------------------------

    run_psql(
        f"""
        SELECT audit.resolve_quarantine(
            {quarantine_id},
            'Corrected ORU received AA and lab result was verified in accepted-result persistence.'
        );
        """
    )

    state = get_quarantine_state(
        quarantine_id
    )

    assert state["status"] == "RESOLVED"
    assert state["resolved_at"] is True
