from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from scripts.hl7.send_mllp import (
    build_mllp_frame,
    get_message_control_id,
    load_hl7_fixture,
    parse_ack,
    remove_mllp_frame,
    send_mllp_frame,
)


@dataclass(frozen=True)
class Hl7TransmissionResult:
    message_control_id: str
    ack_code: str
    ack_control_id: str
    ack_text: str
    round_trip_ms: float

    @property
    def control_id_matches(self) -> bool:
        return (
            self.message_control_id
            == self.ack_control_id
        )

    @property
    def accepted(self) -> bool:
        return self.ack_code == "AA"


def send_hl7_file(
    path: Path,
    *,
    host: str = "127.0.0.1",
    port: int,
    timeout: float = 30.0,
) -> Hl7TransmissionResult:
    """
    Send an HL7 fixture over MLLP and return
    structured acknowledgment evidence.

    The adapter deliberately does not decide whether
    an incident succeeded or failed. It reports what
    happened at the HL7 transport/application-ACK
    boundary.
    """

    segments = load_hl7_fixture(path)

    message_control_id = get_message_control_id(
        segments
    )

    frame = build_mllp_frame(
        segments
    )

    started = perf_counter()

    response = send_mllp_frame(
        frame,
        host=host,
        port=port,
        timeout=timeout,
    )

    round_trip_ms = (
        perf_counter() - started
    ) * 1000.0

    ack_text = remove_mllp_frame(
        response
    )

    ack_code, ack_control_id = parse_ack(
        ack_text
    )

    return Hl7TransmissionResult(
        message_control_id=message_control_id,
        ack_code=ack_code,
        ack_control_id=ack_control_id,
        ack_text=ack_text,
        round_trip_ms=round_trip_ms,
    )
