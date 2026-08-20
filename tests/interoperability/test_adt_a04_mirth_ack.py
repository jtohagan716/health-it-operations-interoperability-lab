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


def replace_message_control_id(
    segments: list[str],
    new_control_id: str,
) -> list[str]:
    updated_segments = segments.copy()

    for index, segment in enumerate(updated_segments):
        if segment.startswith("MSH|"):
            fields = segment.split("|")
            fields[9] = new_control_id
            updated_segments[index] = "|".join(fields)
            return updated_segments

    raise AssertionError("MSH segment not found.")


def test_adt_a04_receives_application_accept_ack():
    segments = load_hl7_fixture(HL7_FIXTURE)

    unique_control_id = (
        "LAB-A04-ACK-"
        f"{uuid4().hex[:12].upper()}"
    )

    segments = replace_message_control_id(
        segments,
        unique_control_id,
    )

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