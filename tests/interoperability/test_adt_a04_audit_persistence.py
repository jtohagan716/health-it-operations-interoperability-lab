import subprocess
import time
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


def create_unique_adt_message(
    control_id_prefix: str = "LAB-A04-TST",
) -> tuple[list[str], dict[str, str]]:
    segments = load_hl7_fixture(HL7_FIXTURE)

    # Work on a copy so the source-controlled fixture remains unchanged.
    segments = segments.copy()

    msh_fields = segments[0].split("|")

    control_id = (
        f"{control_id_prefix}-"
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


def run_mirth_compose(
    *args: str,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    command = [
        "docker",
        "compose",
        "--env-file",
        str(MIRTH_ENV),
        "-f",
        str(MIRTH_COMPOSE),
        *args,
    ]

    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def stop_interop_db() -> None:
    result = run_mirth_compose(
        "stop",
        "interop-db",
    )

    assert result.returncode == 0, (
        "Failed to stop interop-db:\n"
        f"{result.stderr}"
    )


def start_interop_db() -> None:
    result = run_mirth_compose(
        "start",
        "interop-db",
    )

    assert result.returncode == 0, (
        "Failed to start interop-db:\n"
        f"{result.stderr}"
    )


def get_interop_db_container_id() -> str:
    result = run_mirth_compose(
        "ps",
        "-q",
        "interop-db",
    )

    assert result.returncode == 0, (
        "Failed to resolve interop-db container:\n"
        f"{result.stderr}"
    )

    container_id = result.stdout.strip()

    assert container_id, (
        "interop-db container ID was not available"
    )

    return container_id


def get_container_health(container_id: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            container_id,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        return "unavailable"

    return result.stdout.strip()


def wait_for_interop_db_healthy(
    timeout_seconds: float = 120.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status = "unknown"

    while time.monotonic() < deadline:
        try:
            container_id = get_interop_db_container_id()
            last_status = get_container_health(container_id)
        except AssertionError:
            last_status = "unavailable"

        if last_status == "healthy":
            return

        time.sleep(2.0)

    raise AssertionError(
        "interop-db did not become healthy within "
        f"{timeout_seconds:.0f} seconds. "
        f"Last status: {last_status}"
    )


def query_audit_count(
    message_control_id: str,
) -> int:
    env_values = load_env_file(MIRTH_ENV)

    db_user = env_values["INTEROP_DB_USER"]
    db_name = env_values["INTEROP_DB_NAME"]

    sql = f"""
SELECT COUNT(*)
FROM audit.interface_messages
WHERE message_control_id = '{message_control_id}';
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
        "Audit database count query failed:\n"
        f"{result.stderr}"
    )

    return int(result.stdout.strip())

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

def test_adt_a04_downstream_failure_and_recovery():
    wait_for_interop_db_healthy()

    failure_segments, failure_expected = (
        create_unique_adt_message(
            "LAB-A04-FAIL"
        )
    )

    failure_frame = build_mllp_frame(
        failure_segments
    )

    db_stopped = False

    try:
        stop_interop_db()
        db_stopped = True

        response = send_mllp_frame(
            failure_frame,
            host="localhost",
            port=6661,
            timeout=60.0,
        )

        ack_text = remove_mllp_frame(response)

        ack_code, ack_control_id = parse_ack(
            ack_text
        )

        assert ack_code == "AE"
        assert (
            ack_control_id
            == failure_expected["message_control_id"]
        )

    finally:
        if db_stopped:
            start_interop_db()
            wait_for_interop_db_healthy()

    failure_count = query_audit_count(
        failure_expected["message_control_id"]
    )

    assert failure_count == 0

    recovery_segments, recovery_expected = (
        create_unique_adt_message(
            "LAB-A04-RECOVERY"
        )
    )

    recovery_frame = build_mllp_frame(
        recovery_segments
    )

    response = send_mllp_frame(
        recovery_frame,
        host="localhost",
        port=6661,
        timeout=60.0,
    )

    ack_text = remove_mllp_frame(response)

    ack_code, ack_control_id = parse_ack(
        ack_text
    )

    assert ack_code == "AA"
    assert (
        ack_control_id
        == recovery_expected["message_control_id"]
    )

    recovery_row = query_audit_row(
        recovery_expected["message_control_id"]
    )

    assert recovery_row == recovery_expected

def test_duplicate_adt_a04_replay_currently_persists_twice():
    segments, expected = create_unique_adt_message(
        "LAB-A04-REPLAY"
    )

    frame = build_mllp_frame(segments)

    # First delivery.
    first_response = send_mllp_frame(
        frame,
        host="localhost",
        port=6661,
        timeout=60.0,
    )

    first_ack_text = remove_mllp_frame(
        first_response
    )

    first_ack_code, first_ack_control_id = parse_ack(
        first_ack_text
    )

    assert first_ack_code == "AA"
    assert (
        first_ack_control_id
        == expected["message_control_id"]
    )

    first_count = query_audit_count(
        expected["message_control_id"]
    )

    assert first_count == 1

    # Replay the exact same HL7 transaction.
    second_response = send_mllp_frame(
        frame,
        host="localhost",
        port=6661,
        timeout=60.0,
    )

    second_ack_text = remove_mllp_frame(
        second_response
    )

    second_ack_code, second_ack_control_id = parse_ack(
        second_ack_text
    )

    assert second_ack_code == "AA"
    assert (
        second_ack_control_id
        == expected["message_control_id"]
    )

    second_count = query_audit_count(
        expected["message_control_id"]
    )

    assert second_count == 2

def test_same_message_control_id_with_different_patient_is_currently_accepted():
    first_segments, expected = create_unique_adt_message(
        "LAB-A04-CONFLICT"
    )

    message_control_id = expected["message_control_id"]

    # First delivery uses the original synthetic patient.
    first_frame = build_mllp_frame(first_segments)

    first_response = send_mllp_frame(
        first_frame,
        host="localhost",
        port=6661,
        timeout=60.0,
    )

    first_ack_text = remove_mllp_frame(
        first_response
    )

    first_ack_code, first_ack_control_id = parse_ack(
        first_ack_text
    )

    assert first_ack_code == "AA"
    assert first_ack_control_id == message_control_id

    # Create a conflicting version of the same logical
    # HL7 message by retaining MSH-10 but changing PID-3.
    second_segments = first_segments.copy()

    pid_index = next(
        index
        for index, segment in enumerate(second_segments)
        if segment.startswith("PID|")
    )

    pid_fields = second_segments[pid_index].split("|")

    pid_fields[3] = "LAB999999^^^INTEROPLAB^MR"

    second_segments[pid_index] = "|".join(pid_fields)

    second_frame = build_mllp_frame(second_segments)

    second_response = send_mllp_frame(
        second_frame,
        host="localhost",
        port=6661,
        timeout=60.0,
    )

    second_ack_text = remove_mllp_frame(
        second_response
    )

    second_ack_code, second_ack_control_id = parse_ack(
        second_ack_text
    )

    assert second_ack_code == "AA"
    assert second_ack_control_id == message_control_id

    # Current pre-idempotency behavior:
    # both conflicting deliveries are persisted.
    count = query_audit_count(message_control_id)

    assert count == 2