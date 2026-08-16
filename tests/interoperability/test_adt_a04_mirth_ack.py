from pathlib import Path

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


def test_adt_a04_receives_application_accept_ack():
    segments = load_hl7_fixture(HL7_FIXTURE)

    message_control_id = get_message_control_id(segments)

    frame = build_mllp_frame(segments)

    response = send_mllp_frame(
        frame,
        host="localhost",
        port=6661,
        timeout=30.0,
    )

    ack_text = remove_mllp_frame(response)

    ack_code, ack_control_id = parse_ack(ack_text)

    assert ack_code == "AA"
    assert ack_control_id == message_control_id