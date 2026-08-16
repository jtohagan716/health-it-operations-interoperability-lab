import subprocess
import uuid
from pathlib import Path

from scripts.hl7.send_mllp import (
    build_mllp_frame,
    load_hl7_fixture,
    parse_ack,
    remove_mllp_frame,
    send_mllp_frame,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

HL7_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "hl7"
    / "adt"
    / "adt-a04-lab000001.hl7"
)

MIRTH_ENV = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / ".env"
)

MIRTH_COMPOSE = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "compose.yaml"
)


def load_env_file(path: Path) -> dict[str, str]:
    values = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def create_unique_adt_message() -> tuple[list[str], dict[str, str]]:
    segments = load_hl7_fixture(HL7_FIXTURE)

    # Work on a copy so the source-controlled fixture remains unchanged.
    segments = segments.copy()

    msh_fields = segments[0].split("|")

    control_id = (
        "LAB-A04-TST-"
        + uuid.uuid4().hex[:12].upper()
    )

    msh_fields[9] = control_id
    segments[0] = "|".join(msh_fields)

    pid_segment = next(
        segment for segment in segments
        if segment.startswith("PID|")
    )

    pid_fields = pid_segment.split("|")

    expected = {
        "message_control_id": control_id,
        "message_type": msh_fields[8].split("^")[0],
        "trigger_event": msh_fields[8].split("^")[1],
        "patient_identifier": pid_fields[3].split("^")[0],
        "sending_application": msh_fields[2],
        "sending_facility": msh_fields[3],
        "processing_status": "PERSISTED",
    }

    return segments, expected


def query_audit_row(
    message_control_id: str,
) -> dict[str, str]:
    env_values = load_env_file(MIRTH_ENV)

    db_user = env_values["INTEROP_DB_USER"]
    db_name = env_values["INTEROP_DB_NAME"]

    sql = f"""
SELECT
    message_control_id,
    message_type,
    trigger_event,
    patient_identifier,
    sending_application,
    sending_facility,
    processing_status
FROM audit.interface_messages
WHERE message_control_id = '{message_control_id}'
ORDER BY audit_id DESC
LIMIT 1;
""".strip()

    command = [
        "docker",
        "compose",
        "--env-file",
        str(MIRTH_ENV),
        "-f",
        str(MIRTH_COMPOSE),
        "exec",
        "-T",
        "interop-db",
        "psql",
        "-U",
        db_user,
        "-d",
        db_name,
        "-t",
        "-A",
        "-F",
        "|",
        "-c",
        sql,
    ]

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        "Audit database query failed:\n"
        f"{result.stderr}"
    )

    row = result.stdout.strip()

    assert row, (
        "No audit row found for message control ID "
        f"{message_control_id}"
    )

    fields = row.split("|")

    assert len(fields) == 7, (
        f"Unexpected audit row format: {row}"
    )

    return {
        "message_control_id": fields[0],
        "message_type": fields[1],
        "trigger_event": fields[2],
        "patient_identifier": fields[3],
        "sending_application": fields[4],
        "sending_facility": fields[5],
        "processing_status": fields[6],
    }


def test_adt_a04_persists_audit_row_and_returns_aa():
    segments, expected = create_unique_adt_message()

    frame = build_mllp_frame(segments)

    response = send_mllp_frame(
        frame,
        host="localhost",
        port=6661,
        timeout=60.0,
    )

    ack_text = remove_mllp_frame(response)

    ack_code, ack_control_id = parse_ack(ack_text)

    # HL7 application-level validation.
    assert ack_code == "AA"
    assert ack_control_id == expected["message_control_id"]

    # Downstream persistence validation.
    audit_row = query_audit_row(
        expected["message_control_id"]
    )

    assert audit_row == expected