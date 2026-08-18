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
def query_logical_transaction(
    message_control_id: str,
    sending_application: str,
    sending_facility: str,
) -> dict[str, str | int]:
    env_values = load_env_file(MIRTH_ENV)

    db_user = env_values["INTEROP_DB_USER"]
    db_name = env_values["INTEROP_DB_NAME"]

    sql = f"""
SELECT
    transaction_id,
    canonical_payload_sha256,
    receipt_count
FROM audit.interface_transactions
WHERE message_control_id = '{message_control_id}'
  AND sending_application = '{sending_application}'
  AND sending_facility = '{sending_facility}';
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
        "Logical transaction query failed:\n"
        f"{result.stderr}"
    )

    row = result.stdout.strip()

    assert row, (
        "No logical transaction found for message identity "
        f"{sending_application}/"
        f"{sending_facility}/"
        f"{message_control_id}"
    )

    fields = row.split("|")

    assert len(fields) == 3, (
        f"Unexpected logical transaction row: {row}"
    )

    return {
        "transaction_id": int(fields[0]),
        "canonical_payload_sha256": fields[1],
        "receipt_count": int(fields[2]),
    }


def query_receipt_attempts(
    message_control_id: str,
    sending_application: str,
    sending_facility: str,
) -> list[dict[str, str | int]]:
    env_values = load_env_file(MIRTH_ENV)

    db_user = env_values["INTEROP_DB_USER"]
    db_name = env_values["INTEROP_DB_NAME"]

    sql = f"""
SELECT
    m.audit_id,
    m.transaction_id,
    m.patient_identifier,
    m.payload_sha256,
    m.attempt_outcome,
    m.processing_status
FROM audit.interface_messages m
JOIN audit.interface_transactions t
    ON t.transaction_id = m.transaction_id
WHERE t.message_control_id = '{message_control_id}'
  AND t.sending_application = '{sending_application}'
  AND t.sending_facility = '{sending_facility}'
ORDER BY m.audit_id;
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
        "Receipt attempt query failed:\n"
        f"{result.stderr}"
    )

    rows = [
        row
        for row in result.stdout.splitlines()
        if row.strip()
    ]

    attempts = []

    for row in rows:
        fields = row.split("|")

        assert len(fields) == 6, (
            f"Unexpected receipt attempt row: {row}"
        )

        attempts.append(
            {
                "audit_id": int(fields[0]),
                "transaction_id": int(fields[1]),
                "patient_identifier": fields[2],
                "payload_sha256": fields[3],
                "attempt_outcome": fields[4],
                "processing_status": fields[5],
            }
        )

    return attempts

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

def test_duplicate_adt_a04_replay_is_classified_as_exact_replay():
    segments, expected = create_unique_adt_message(
        "LAB-A04-REPLAY"
    )

    frame = build_mllp_frame(segments)

    message_control_id = expected["message_control_id"]
    sending_application = expected["sending_application"]
    sending_facility = expected["sending_facility"]

    # First delivery establishes the canonical logical transaction.
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
    assert first_ack_control_id == message_control_id

    first_transaction = query_logical_transaction(
        message_control_id,
        sending_application,
        sending_facility,
    )

    first_attempts = query_receipt_attempts(
        message_control_id,
        sending_application,
        sending_facility,
    )

    assert first_transaction["receipt_count"] == 1

    assert len(
        first_transaction["canonical_payload_sha256"]
    ) == 64

    assert len(first_attempts) == 1

    assert (
        first_attempts[0]["transaction_id"]
        == first_transaction["transaction_id"]
    )

    assert (
        first_attempts[0]["patient_identifier"]
        == expected["patient_identifier"]
    )

    assert (
        first_attempts[0]["payload_sha256"]
        == first_transaction["canonical_payload_sha256"]
    )

    assert (
        first_attempts[0]["attempt_outcome"]
        == "FIRST_DELIVERY"
    )

    assert (
        first_attempts[0]["processing_status"]
        == "PERSISTED"
    )

    canonical_hash = (
        first_transaction["canonical_payload_sha256"]
    )

    logical_transaction_id = (
        first_transaction["transaction_id"]
    )

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
    assert second_ack_control_id == message_control_id

    second_transaction = query_logical_transaction(
        message_control_id,
        sending_application,
        sending_facility,
    )

    second_attempts = query_receipt_attempts(
        message_control_id,
        sending_application,
        sending_facility,
    )

    # The replay must remain associated with the original
    # logical transaction rather than creating a new one.
    assert (
        second_transaction["transaction_id"]
        == logical_transaction_id
    )

    assert second_transaction["receipt_count"] == 2

    # The original payload remains canonical.
    assert (
        second_transaction["canonical_payload_sha256"]
        == canonical_hash
    )

    assert len(second_attempts) == 2

    assert (
        second_attempts[0]["transaction_id"]
        == logical_transaction_id
    )

    assert (
        second_attempts[1]["transaction_id"]
        == logical_transaction_id
    )

    assert (
        second_attempts[0]["attempt_outcome"]
        == "FIRST_DELIVERY"
    )

    assert (
        second_attempts[1]["attempt_outcome"]
        == "EXACT_REPLAY"
    )

    # Exact replay means both observed receipts have the
    # same payload fingerprint as the canonical transaction.
    assert (
        second_attempts[0]["payload_sha256"]
        == canonical_hash
    )

    assert (
        second_attempts[1]["payload_sha256"]
        == canonical_hash
    )

    assert (
        second_attempts[0]["patient_identifier"]
        == expected["patient_identifier"]
    )

    assert (
        second_attempts[1]["patient_identifier"]
        == expected["patient_identifier"]
    )

    assert all(
        attempt["processing_status"] == "PERSISTED"
        for attempt in second_attempts
    )

def test_same_message_identity_with_different_payload_is_rejected_as_conflict():
    first_segments, expected = create_unique_adt_message(
        "LAB-A04-CONFLICT"
    )

    message_control_id = expected["message_control_id"]
    sending_application = expected["sending_application"]
    sending_facility = expected["sending_facility"]

    # First delivery establishes the canonical transaction.
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

    first_transaction = query_logical_transaction(
        message_control_id,
        sending_application,
        sending_facility,
    )

    first_attempts = query_receipt_attempts(
        message_control_id,
        sending_application,
        sending_facility,
    )

    assert first_transaction["receipt_count"] == 1
    assert len(first_attempts) == 1

    assert (
        first_attempts[0]["attempt_outcome"]
        == "FIRST_DELIVERY"
    )

    canonical_hash = (
        first_transaction["canonical_payload_sha256"]
    )

    logical_transaction_id = (
        first_transaction["transaction_id"]
    )

    assert (
        first_attempts[0]["payload_sha256"]
        == canonical_hash
    )

    # Create a conflicting representation of the same
    # logical HL7 transaction by retaining MSH-10 while
    # changing PID-3.
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

    # Conflicting reuse is a deliberate application rejection.
    # The receipt must remain auditable, but the conflicting
    # transaction must not be accepted for business processing.
    assert second_ack_code == "AR"
    assert second_ack_control_id == message_control_id

    second_transaction = query_logical_transaction(
        message_control_id,
        sending_application,
        sending_facility,
    )

    second_attempts = query_receipt_attempts(
        message_control_id,
        sending_application,
        sending_facility,
    )

    # Both receipts must remain associated with the same
    # logical transaction identity.
    assert (
        second_transaction["transaction_id"]
        == logical_transaction_id
    )

    assert second_transaction["receipt_count"] == 2

    # Conflicting content must never replace the original
    # canonical payload.
    assert (
        second_transaction["canonical_payload_sha256"]
        == canonical_hash
    )

    assert len(second_attempts) == 2

    assert (
        second_attempts[0]["transaction_id"]
        == logical_transaction_id
    )

    assert (
        second_attempts[1]["transaction_id"]
        == logical_transaction_id
    )

    assert (
        second_attempts[0]["attempt_outcome"]
        == "FIRST_DELIVERY"
    )

    assert (
        second_attempts[1]["attempt_outcome"]
        == "CONFLICTING_REUSE"
    )

    assert (
        second_attempts[0]["patient_identifier"]
        == expected["patient_identifier"]
    )

    assert (
        second_attempts[1]["patient_identifier"]
        == "LAB999999"
    )

    # Different payload content must produce a different
    # fingerprint while leaving canonical state unchanged.
    assert (
        second_attempts[0]["payload_sha256"]
        == canonical_hash
    )

    assert (
        second_attempts[1]["payload_sha256"]
        != canonical_hash
    )

    assert (
        second_attempts[0]["processing_status"]
        == "PERSISTED"
    )

    assert (
        second_attempts[1]["processing_status"]
        == "REJECTED"
    )
