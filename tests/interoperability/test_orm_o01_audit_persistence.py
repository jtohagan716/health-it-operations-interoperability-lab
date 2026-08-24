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
    / "orm"
    / "orm-o01-rad000001.hl7"
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

MIRTH_ORM_PORT = 6663


def load_env_file(path: Path) -> dict[str, str]:
    values = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_psql(sql: str) -> list[str]:
    env_values = load_env_file(MIRTH_ENV)

    db_user = env_values["INTEROP_DB_USER"]
    db_name = env_values["INTEROP_DB_NAME"]

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
        "-v",
        "ON_ERROR_STOP=1",
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
        "Interop database query failed:\n"
        f"{result.stderr}"
    )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def create_unique_orm_message(
    control_id_prefix: str = "RAD-ORM-TST",
) -> tuple[list[str], dict[str, str]]:
    segments = load_hl7_fixture(HL7_FIXTURE).copy()

    suffix = uuid.uuid4().hex[:10].upper()

    msh_index = next(
        index
        for index, segment in enumerate(segments)
        if segment.startswith("MSH|")
    )
    pid_index = next(
        index
        for index, segment in enumerate(segments)
        if segment.startswith("PID|")
    )
    orc_index = next(
        index
        for index, segment in enumerate(segments)
        if segment.startswith("ORC|")
    )
    obr_index = next(
        index
        for index, segment in enumerate(segments)
        if segment.startswith("OBR|")
    )

    msh_fields = segments[msh_index].split("|")
    pid_fields = segments[pid_index].split("|")
    orc_fields = segments[orc_index].split("|")
    obr_fields = segments[obr_index].split("|")

    message_control_id = f"{control_id_prefix}-{suffix}"
    placer_order_number = f"RADORD{suffix}"
    accession_number = f"RAD{suffix}"

    msh_fields[9] = message_control_id

    # ORC-2 / OBR-2 = placer order number.
    # ORC-3 / OBR-3 = filler order number.
    # In this lab contract, the filler order number also serves as
    # the radiology accession number used later for DICOM correlation.
    orc_fields[2] = placer_order_number
    orc_fields[3] = accession_number
    obr_fields[2] = placer_order_number
    obr_fields[3] = accession_number

    segments[msh_index] = "|".join(msh_fields)
    segments[orc_index] = "|".join(orc_fields)
    segments[obr_index] = "|".join(obr_fields)

    procedure = obr_fields[4].split("^")

    expected = {
        "message_control_id": message_control_id,
        "patient_identifier": pid_fields[3].split("^")[0],
        "sending_application": msh_fields[2],
        "sending_facility": msh_fields[3],
        "placer_order_number": placer_order_number,
        "filler_order_number": accession_number,
        "accession_number": accession_number,
        "procedure_code": procedure[0],
        "procedure_text": procedure[1],
    }

    return segments, expected


def send_orm(
    segments: list[str],
) -> tuple[str, str]:
    frame = build_mllp_frame(segments)

    response = send_mllp_frame(
        frame,
        host="localhost",
        port=MIRTH_ORM_PORT,
        timeout=60.0,
    )

    ack_text = remove_mllp_frame(response)
    return parse_ack(ack_text)


def query_logical_transaction(
    expected: dict[str, str],
) -> dict[str, str | int]:
    sql = f"""
SELECT
    transaction_id,
    canonical_payload_sha256,
    receipt_count
FROM audit.interface_transactions
WHERE message_control_id = {sql_literal(expected["message_control_id"])}
  AND sending_application = {sql_literal(expected["sending_application"])}
  AND sending_facility = {sql_literal(expected["sending_facility"])};
""".strip()

    rows = run_psql(sql)

    assert len(rows) == 1, (
        "Expected exactly one logical transaction, found "
        f"{len(rows)}: {rows}"
    )

    fields = rows[0].split("|")

    assert len(fields) == 3, (
        f"Unexpected logical transaction row: {rows[0]}"
    )

    return {
        "transaction_id": int(fields[0]),
        "canonical_payload_sha256": fields[1],
        "receipt_count": int(fields[2]),
    }


def query_receipt_attempts(
    expected: dict[str, str],
) -> list[dict[str, str | int]]:
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
WHERE t.message_control_id = {sql_literal(expected["message_control_id"])}
  AND t.sending_application = {sql_literal(expected["sending_application"])}
  AND t.sending_facility = {sql_literal(expected["sending_facility"])}
ORDER BY m.audit_id;
""".strip()

    rows = run_psql(sql)
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


def query_orm_order(
    transaction_id: int,
) -> dict[str, str | int]:
    sql = f"""
SELECT
    transaction_id,
    message_control_id,
    patient_identifier,
    placer_order_number,
    filler_order_number,
    accession_number,
    procedure_code,
    procedure_text
FROM audit.orm_orders
WHERE transaction_id = {transaction_id};
""".strip()

    rows = run_psql(sql)

    assert len(rows) == 1, (
        "Expected exactly one canonical ORM order for transaction "
        f"{transaction_id}, found {len(rows)}: {rows}"
    )

    fields = rows[0].split("|")

    assert len(fields) == 8, (
        f"Unexpected ORM order row: {rows[0]}"
    )

    return {
        "transaction_id": int(fields[0]),
        "message_control_id": fields[1],
        "patient_identifier": fields[2],
        "placer_order_number": fields[3],
        "filler_order_number": fields[4],
        "accession_number": fields[5],
        "procedure_code": fields[6],
        "procedure_text": fields[7],
    }


def query_orm_order_count(
    transaction_id: int,
) -> int:
    sql = f"""
SELECT COUNT(*)
FROM audit.orm_orders
WHERE transaction_id = {transaction_id};
""".strip()

    rows = run_psql(sql)

    assert len(rows) == 1, (
        f"Unexpected ORM count result: {rows}"
    )

    return int(rows[0])


def delete_orm_order(
    transaction_id: int,
) -> None:
    sql = f"""
DELETE FROM audit.orm_orders
WHERE transaction_id = {transaction_id};
""".strip()

    run_psql(sql)


def assert_order_matches_expected(
    order: dict[str, str | int],
    expected: dict[str, str],
    transaction_id: int,
) -> None:
    assert order == {
        "transaction_id": transaction_id,
        "message_control_id": expected["message_control_id"],
        "patient_identifier": expected["patient_identifier"],
        "placer_order_number": expected["placer_order_number"],
        "filler_order_number": expected["filler_order_number"],
        "accession_number": expected["accession_number"],
        "procedure_code": expected["procedure_code"],
        "procedure_text": expected["procedure_text"],
    }


def test_orm_o01_persists_canonical_order_and_returns_aa():
    segments, expected = create_unique_orm_message()

    ack_code, ack_control_id = send_orm(segments)

    assert ack_code == "AA"
    assert ack_control_id == expected["message_control_id"]

    transaction = query_logical_transaction(expected)
    transaction_id = transaction["transaction_id"]

    assert transaction["receipt_count"] == 1
    assert len(transaction["canonical_payload_sha256"]) == 64

    attempts = query_receipt_attempts(expected)

    assert len(attempts) == 1
    assert attempts[0]["transaction_id"] == transaction_id
    assert attempts[0]["patient_identifier"] == expected["patient_identifier"]
    assert (
        attempts[0]["payload_sha256"]
        == transaction["canonical_payload_sha256"]
    )
    assert attempts[0]["attempt_outcome"] == "FIRST_DELIVERY"
    assert attempts[0]["processing_status"] == "PERSISTED"

    assert query_orm_order_count(transaction_id) == 1

    order = query_orm_order(transaction_id)
    assert_order_matches_expected(
        order,
        expected,
        transaction_id,
    )


def test_duplicate_orm_o01_replay_reuses_transaction_and_business_row():
    segments, expected = create_unique_orm_message(
        "RAD-ORM-REPLAY"
    )

    first_ack_code, first_ack_control_id = send_orm(segments)

    assert first_ack_code == "AA"
    assert first_ack_control_id == expected["message_control_id"]

    first_transaction = query_logical_transaction(expected)
    transaction_id = first_transaction["transaction_id"]
    canonical_hash = first_transaction["canonical_payload_sha256"]

    assert first_transaction["receipt_count"] == 1
    assert query_orm_order_count(transaction_id) == 1

    original_order = query_orm_order(transaction_id)

    second_ack_code, second_ack_control_id = send_orm(segments)

    assert second_ack_code == "AA"
    assert second_ack_control_id == expected["message_control_id"]

    second_transaction = query_logical_transaction(expected)

    assert second_transaction["transaction_id"] == transaction_id
    assert second_transaction["receipt_count"] == 2
    assert second_transaction["canonical_payload_sha256"] == canonical_hash

    attempts = query_receipt_attempts(expected)

    assert len(attempts) == 2
    assert [attempt["attempt_outcome"] for attempt in attempts] == [
        "FIRST_DELIVERY",
        "EXACT_REPLAY",
    ]
    assert all(
        attempt["transaction_id"] == transaction_id
        for attempt in attempts
    )
    assert all(
        attempt["payload_sha256"] == canonical_hash
        for attempt in attempts
    )
    assert all(
        attempt["processing_status"] == "PERSISTED"
        for attempt in attempts
    )

    # Exact replay is idempotent: one canonical business row remains.
    assert query_orm_order_count(transaction_id) == 1
    assert query_orm_order(transaction_id) == original_order


def test_same_orm_identity_with_different_payload_is_rejected_without_mutating_order():
    first_segments, expected = create_unique_orm_message(
        "RAD-ORM-CONFLICT"
    )

    first_ack_code, first_ack_control_id = send_orm(
        first_segments
    )

    assert first_ack_code == "AA"
    assert first_ack_control_id == expected["message_control_id"]

    first_transaction = query_logical_transaction(expected)
    transaction_id = first_transaction["transaction_id"]
    canonical_hash = first_transaction["canonical_payload_sha256"]
    canonical_order = query_orm_order(transaction_id)

    # Keep MSH-10 unchanged but alter valid clinical content.
    # This is conflicting reuse of the same logical message identity.
    second_segments = first_segments.copy()

    pid_index = next(
        index
        for index, segment in enumerate(second_segments)
        if segment.startswith("PID|")
    )

    pid_fields = second_segments[pid_index].split("|")
    pid_fields[3] = "LAB999999^^^INTEROPLAB^MR"
    second_segments[pid_index] = "|".join(pid_fields)

    second_ack_code, second_ack_control_id = send_orm(
        second_segments
    )

    assert second_ack_code == "AR"
    assert second_ack_control_id == expected["message_control_id"]

    second_transaction = query_logical_transaction(expected)

    assert second_transaction["transaction_id"] == transaction_id
    assert second_transaction["receipt_count"] == 2
    assert second_transaction["canonical_payload_sha256"] == canonical_hash

    attempts = query_receipt_attempts(expected)

    assert len(attempts) == 2
    assert attempts[0]["attempt_outcome"] == "FIRST_DELIVERY"
    assert attempts[0]["processing_status"] == "PERSISTED"
    assert attempts[0]["patient_identifier"] == expected["patient_identifier"]
    assert attempts[0]["payload_sha256"] == canonical_hash

    assert attempts[1]["attempt_outcome"] == "CONFLICTING_REUSE"
    assert attempts[1]["processing_status"] == "REJECTED"
    assert attempts[1]["patient_identifier"] == "LAB999999"
    assert attempts[1]["payload_sha256"] != canonical_hash

    # Conflicting content cannot replace or duplicate canonical order state.
    assert query_orm_order_count(transaction_id) == 1
    assert query_orm_order(transaction_id) == canonical_order


def test_exact_replay_repairs_missing_orm_business_row():
    segments, expected = create_unique_orm_message(
        "RAD-ORM-REPAIR"
    )

    first_ack_code, first_ack_control_id = send_orm(segments)

    assert first_ack_code == "AA"
    assert first_ack_control_id == expected["message_control_id"]

    first_transaction = query_logical_transaction(expected)
    transaction_id = first_transaction["transaction_id"]
    canonical_hash = first_transaction["canonical_payload_sha256"]

    assert first_transaction["receipt_count"] == 1
    assert query_orm_order_count(transaction_id) == 1

    original_order = query_orm_order(transaction_id)

    # Controlled simulation of the real partial-failure condition:
    # the generic receipt transaction survives, but the canonical
    # downstream ORM business row is absent.
    delete_orm_order(transaction_id)

    assert query_orm_order_count(transaction_id) == 0

    replay_ack_code, replay_ack_control_id = send_orm(segments)

    assert replay_ack_code == "AA"
    assert replay_ack_control_id == expected["message_control_id"]

    replay_transaction = query_logical_transaction(expected)

    # Recovery must reuse the original logical transaction.
    assert replay_transaction["transaction_id"] == transaction_id
    assert replay_transaction["receipt_count"] == 2
    assert replay_transaction["canonical_payload_sha256"] == canonical_hash

    attempts = query_receipt_attempts(expected)

    assert len(attempts) == 2
    assert [attempt["attempt_outcome"] for attempt in attempts] == [
        "FIRST_DELIVERY",
        "EXACT_REPLAY",
    ]
    assert all(
        attempt["transaction_id"] == transaction_id
        for attempt in attempts
    )
    assert all(
        attempt["processing_status"] == "PERSISTED"
        for attempt in attempts
    )

    # Exact replay repairs the missing canonical business row
    # instead of creating a second logical transaction.
    assert query_orm_order_count(transaction_id) == 1

    repaired_order = query_orm_order(transaction_id)

    assert repaired_order == original_order
    assert_order_matches_expected(
        repaired_order,
        expected,
        transaction_id,
    )
