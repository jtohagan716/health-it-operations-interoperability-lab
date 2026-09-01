import subprocess
import time
from dataclasses import dataclass
from uuid import uuid4

from scripts.hl7.send_mllp import (
    build_mllp_frame,
    get_message_control_id,
    parse_ack,
    remove_mllp_frame,
    send_mllp_frame,
)


DEFAULT_INTEROP_DB_CONTAINER = (
    "health-it-mirth-lab-interop-db-1"
)
DEFAULT_INTEROP_DB_USER = "interop_app"
DEFAULT_INTEROP_DB_NAME = "interop"


@dataclass(frozen=True)
class Acknowledgment:
    text: str
    code: str
    control_id: str
    round_trip_seconds: float

    @property
    def accepted(self) -> bool:
        return self.code == "AA"


def generate_control_id(
    prefix: str,
    *,
    suffix_length: int = 12,
) -> str:
    normalized_prefix = prefix.strip()

    if not normalized_prefix:
        raise ValueError(
            "Message control ID prefix must not be blank."
        )

    if suffix_length <= 0:
        raise ValueError(
            "Message control ID suffix length must be positive."
        )

    suffix = uuid4().hex[
        :suffix_length
    ].upper()

    return f"{normalized_prefix}-{suffix}"


def replace_segment_field(
    segments: list[str],
    *,
    segment_name: str,
    field_index: int,
    new_value: str,
    occurrence: int = 0,
) -> list[str]:
    if field_index < 0:
        raise ValueError(
            "HL7 field index must not be negative."
        )

    if occurrence < 0:
        raise ValueError(
            "Segment occurrence must not be negative."
        )

    updated = segments.copy()
    matching_occurrence = 0
    segment_prefix = f"{segment_name}|"

    for index, segment in enumerate(updated):
        if not segment.startswith(segment_prefix):
            continue

        if matching_occurrence != occurrence:
            matching_occurrence += 1
            continue

        fields = segment.split("|")

        if len(fields) <= field_index:
            raise ValueError(
                f"{segment_name} segment does not contain "
                f"field index {field_index}."
            )

        fields[field_index] = new_value
        updated[index] = "|".join(fields)

        return updated

    raise ValueError(
        f"{segment_name} occurrence {occurrence} was not found."
    )


def replace_message_control_id(
    segments: list[str],
    new_control_id: str,
) -> list[str]:
    return replace_segment_field(
        segments,
        segment_name="MSH",
        field_index=9,
        new_value=new_control_id,
    )


def replace_observation_value(
    segments: list[str],
    new_value: str,
    *,
    occurrence: int = 0,
) -> list[str]:
    return replace_segment_field(
        segments,
        segment_name="OBX",
        field_index=5,
        new_value=new_value,
        occurrence=occurrence,
    )


def send_segments(
    segments: list[str],
    *,
    host: str,
    port: int,
    timeout: float = 30.0,
) -> Acknowledgment:
    expected_control_id = get_message_control_id(
        segments
    )

    frame = build_mllp_frame(segments)

    started = time.perf_counter()

    response = send_mllp_frame(
        frame,
        host=host,
        port=port,
        timeout=timeout,
    )

    elapsed = time.perf_counter() - started

    ack_text = remove_mllp_frame(response)
    ack_code, ack_control_id = parse_ack(ack_text)

    if ack_control_id != expected_control_id:
        raise RuntimeError(
            "ACK correlation failed: "
            f"expected MSA-2 {expected_control_id}, "
            f"received {ack_control_id}."
        )

    return Acknowledgment(
        text=ack_text,
        code=ack_code,
        control_id=ack_control_id,
        round_trip_seconds=elapsed,
    )


def run_psql(
    query: str,
    *,
    container: str = DEFAULT_INTEROP_DB_CONTAINER,
    user: str = DEFAULT_INTEROP_DB_USER,
    database: str = DEFAULT_INTEROP_DB_NAME,
) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            user,
            "-d",
            database,
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

    if result.returncode != 0:
        raise RuntimeError(
            "PostgreSQL command failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result.stdout.strip()
