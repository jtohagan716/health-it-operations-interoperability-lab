from pathlib import Path
import uuid

from scripts.hl7.send_mllp import (
    build_mllp_frame,
    get_message_control_id,
    load_hl7_fixture,
    parse_ack,
    remove_mllp_frame,
    send_mllp_frame,
)
from scripts.radiology.persist_lineage import (
    run_interop_db_sql,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_ORM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "orm-rad-workflow-000001.hl7"
)

MIRTH_HOST = "127.0.0.1"
MIRTH_ORM_PORT = 6663


def create_isolated_orm_fixture(
    tmp_path: Path,
) -> tuple[Path, dict[str, str]]:
    """
    Create a disposable ORM^O01 imaging order with unique
    interface and business identifiers.

    The unique identifiers ensure that repeated test runs
    cannot collide with:
      * documentation transactions,
      * prior test runs,
      * replay-detection state,
      * persistent radiology evidence.
    """

    suffix = uuid.uuid4().hex[:10].upper()

    control_id = (
        f"RAD-ORM-RUNTIME-{suffix}"
    )

    patient_id = (
        f"RADRT{suffix}"
    )

    placer_order = (
        f"RADORD{suffix}"
    )

    accession = (
        f"RAD{suffix}"
    )

    fixture_text = BASE_ORM_FIXTURE.read_text(
        encoding="ascii"
    )

    fixture_text = fixture_text.replace(
        "RAD-ORM-WORKFLOW-000001",
        control_id,
    )

    fixture_text = fixture_text.replace(
        "RADPAT000001",
        patient_id,
    )

    fixture_text = fixture_text.replace(
        "RADORD000001",
        placer_order,
    )

    fixture_text = fixture_text.replace(
        "RAD000001",
        accession,
    )

    fixture_path = (
        tmp_path
        / "orm-radiology-runtime.hl7"
    )

    fixture_path.write_text(
        fixture_text,
        encoding="ascii",
    )

    expected = {
        "control_id": control_id,
        "patient_id": patient_id,
        "placer_order": placer_order,
        "accession": accession,
        "procedure_code": "XRCH2",
        "procedure_text": "Chest X-ray 2 Views",
    }

    return fixture_path, expected


def test_radiology_orm_traverses_mirth_and_persists():
    """
    Runtime integration contract.

    A unique ORM^O01 imaging order must:

      1. traverse TCP/MLLP to the running Mirth channel,
      2. receive an AA application acknowledgment,
      3. correlate MSA-2 to the request MSH-10,
      4. create exactly one canonical interface transaction,
      5. create exactly one normalized ORM business order,
      6. preserve patient/order/accession/procedure identity,
      7. clean up only its own disposable database state.
    """

    import tempfile

    transaction_id = None

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)

        (
            fixture_path,
            expected,
        ) = create_isolated_orm_fixture(
            tmp_path
        )

        try:
            # -------------------------------------------------
            # Build and send the real HL7 MLLP transaction.
            # -------------------------------------------------

            segments = load_hl7_fixture(
                fixture_path
            )

            control_id = get_message_control_id(
                segments
            )

            assert (
                control_id
                == expected["control_id"]
            )

            frame = build_mllp_frame(
                segments
            )

            response = send_mllp_frame(
                frame,
                host=MIRTH_HOST,
                port=MIRTH_ORM_PORT,
                timeout=15.0,
            )

            # -------------------------------------------------
            # Validate the application acknowledgment.
            # -------------------------------------------------

            ack_text = remove_mllp_frame(
                response
            )

            (
                ack_code,
                ack_control_id,
            ) = parse_ack(
                ack_text
            )

            assert ack_code == "AA"

            assert (
                ack_control_id
                == expected["control_id"]
            )

            # -------------------------------------------------
            # Verify canonical interface transaction state.
            #
            # This is intentionally checked independently
            # from the ACK. An AA alone is not sufficient
            # evidence that persistence is correct.
            # -------------------------------------------------

            transaction_output = (
                run_interop_db_sql(
                    f"""
SELECT
    transaction_id,
    sending_application,
    sending_facility,
    message_control_id,
    receipt_count,
    length(canonical_payload_sha256)
FROM audit.interface_transactions
WHERE sending_application = 'EHR'
  AND sending_facility = 'INTEROPLAB'
  AND message_control_id =
      '{expected["control_id"]}';
""".strip()
                )
            )

            transaction_fields = (
                transaction_output.split("|")
            )

            assert (
                len(transaction_fields)
                == 6
            )

            transaction_id = int(
                transaction_fields[0]
            )

            assert transaction_id > 0

            assert (
                transaction_fields[1]
                == "EHR"
            )

            assert (
                transaction_fields[2]
                == "INTEROPLAB"
            )

            assert (
                transaction_fields[3]
                == expected["control_id"]
            )

            # This was one deliberate delivery.
            assert (
                transaction_fields[4]
                == "1"
            )

            # SHA-256 must be represented by exactly
            # 64 hexadecimal characters.
            assert (
                transaction_fields[5]
                == "64"
            )

            # -------------------------------------------------
            # Verify normalized ORM business persistence.
            # -------------------------------------------------

            orm_output = run_interop_db_sql(
                f"""
SELECT
    transaction_id,
    message_control_id,
    patient_identifier,
    placer_order_number,
    filler_order_number,
    accession_number,
    order_control,
    order_status,
    procedure_code,
    procedure_text
FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};
""".strip()
            )

            orm_fields = orm_output.split("|")

            assert len(orm_fields) == 10

            assert (
                int(orm_fields[0])
                == transaction_id
            )

            assert (
                orm_fields[1]
                == expected["control_id"]
            )

            assert (
                orm_fields[2]
                == expected["patient_id"]
            )

            assert (
                orm_fields[3]
                == expected["placer_order"]
            )

            assert (
                orm_fields[4]
                == expected["accession"]
            )

            assert (
                orm_fields[5]
                == expected["accession"]
            )

            assert (
                orm_fields[6]
                == "NW"
            )

            assert (
                orm_fields[7]
                == "SC"
            )

            assert (
                orm_fields[8]
                == expected["procedure_code"]
            )

            assert (
                orm_fields[9]
                == expected["procedure_text"]
            )

        finally:
            # -------------------------------------------------
            # Remove only the disposable transaction created
            # by this test.
            #
            # orm_orders must be removed first because its
            # transaction_id references interface_transactions.
            # -------------------------------------------------

            if transaction_id is not None:
                run_interop_db_sql(
                    f"""
DELETE FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};

DELETE FROM audit.interface_messages
WHERE transaction_id =
      {transaction_id};

DELETE FROM audit.interface_transactions
WHERE transaction_id =
      {transaction_id};
""".strip()
                )

def test_exact_replay_reuses_canonical_orm_transaction():
    import tempfile

    transaction_id = None

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)

        (
            fixture_path,
            expected,
        ) = create_isolated_orm_fixture(
            tmp_path
        )

        try:
            segments = load_hl7_fixture(
                fixture_path
            )

            frame = build_mllp_frame(
                segments
            )

            # First delivery
            first_response = send_mllp_frame(
                frame,
                host=MIRTH_HOST,
                port=MIRTH_ORM_PORT,
                timeout=15.0,
            )

            first_ack = remove_mllp_frame(
                first_response
            )

            (
                first_ack_code,
                first_ack_control_id,
            ) = parse_ack(
                first_ack
            )

            assert first_ack_code == "AA"

            assert (
                first_ack_control_id
                == expected["control_id"]
            )

            first_state = run_interop_db_sql(
                f"""
SELECT
    transaction_id,
    receipt_count
FROM audit.interface_transactions
WHERE sending_application = 'EHR'
  AND sending_facility = 'INTEROPLAB'
  AND message_control_id =
      '{expected["control_id"]}';
""".strip()
            )

            first_fields = first_state.split("|")

            transaction_id = int(
                first_fields[0]
            )

            assert first_fields[1] == "1"

            # Exact replay: same bytes, same control ID,
            # same canonical payload hash.
            second_response = send_mllp_frame(
                frame,
                host=MIRTH_HOST,
                port=MIRTH_ORM_PORT,
                timeout=15.0,
            )

            second_ack = remove_mllp_frame(
                second_response
            )

            (
                second_ack_code,
                second_ack_control_id,
            ) = parse_ack(
                second_ack
            )

            assert second_ack_code == "AA"

            assert (
                second_ack_control_id
                == expected["control_id"]
            )

            second_state = run_interop_db_sql(
                f"""
SELECT
    transaction_id,
    receipt_count
FROM audit.interface_transactions
WHERE sending_application = 'EHR'
  AND sending_facility = 'INTEROPLAB'
  AND message_control_id =
      '{expected["control_id"]}';
""".strip()
            )

            second_fields = second_state.split("|")

            assert (
                int(second_fields[0])
                == transaction_id
            )

            assert second_fields[1] == "2"

            orm_count = run_interop_db_sql(
                f"""
SELECT count(*)
FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};
""".strip()
            )

            assert orm_count == "1"

        finally:
            if transaction_id is not None:
                run_interop_db_sql(
                    f"""
DELETE FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};

DELETE FROM audit.interface_messages
WHERE transaction_id =
      {transaction_id};

DELETE FROM audit.interface_transactions
WHERE transaction_id =
      {transaction_id};
""".strip()
                )

def test_conflicting_control_id_reuse_is_rejected():
    import tempfile

    transaction_id = None

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)

        (
            fixture_path,
            expected,
        ) = create_isolated_orm_fixture(
            tmp_path
        )

        try:
            # -------------------------------------------------
            # First canonical delivery.
            # -------------------------------------------------

            segments = load_hl7_fixture(
                fixture_path
            )

            frame = build_mllp_frame(
                segments
            )

            first_response = send_mllp_frame(
                frame,
                host=MIRTH_HOST,
                port=MIRTH_ORM_PORT,
                timeout=15.0,
            )

            first_ack = remove_mllp_frame(
                first_response
            )

            (
                first_ack_code,
                first_ack_control_id,
            ) = parse_ack(
                first_ack
            )

            assert first_ack_code == "AA"

            assert (
                first_ack_control_id
                == expected["control_id"]
            )

            # -------------------------------------------------
            # Capture canonical transaction and order state.
            # -------------------------------------------------

            canonical_transaction = (
                run_interop_db_sql(
                    f"""
SELECT
    transaction_id,
    canonical_payload_sha256,
    receipt_count
FROM audit.interface_transactions
WHERE sending_application = 'EHR'
  AND sending_facility = 'INTEROPLAB'
  AND message_control_id =
      '{expected["control_id"]}';
""".strip()
                )
            )

            canonical_fields = (
                canonical_transaction.split("|")
            )

            transaction_id = int(
                canonical_fields[0]
            )

            canonical_hash = (
                canonical_fields[1]
            )

            assert canonical_fields[2] == "1"

            canonical_order = (
                run_interop_db_sql(
                    f"""
SELECT
    patient_identifier,
    placer_order_number,
    filler_order_number,
    accession_number,
    procedure_code,
    procedure_text
FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};
""".strip()
                )
            )

            canonical_order_fields = (
                canonical_order.split("|")
            )

            # -------------------------------------------------
            # Build conflicting payload.
            #
            # Crucially:
            # MSH-10 remains identical.
            #
            # The clinical payload changes, so this is NOT an
            # exact replay.
            # -------------------------------------------------

            conflicting_text = (
                fixture_path.read_text(
                    encoding="ascii"
                )
            )

            conflicting_patient = (
                expected["patient_id"]
                + "CONFLICT"
            )

            conflicting_text = (
                conflicting_text.replace(
                    expected["patient_id"],
                    conflicting_patient,
                )
            )

            conflicting_path = (
                tmp_path
                / "orm-radiology-conflict.hl7"
            )

            conflicting_path.write_text(
                conflicting_text,
                encoding="ascii",
            )

            conflicting_segments = (
                load_hl7_fixture(
                    conflicting_path
                )
            )

            conflicting_control_id = (
                get_message_control_id(
                    conflicting_segments
                )
            )

            # Same logical transaction identity.
            assert (
                conflicting_control_id
                == expected["control_id"]
            )

            conflicting_frame = (
                build_mllp_frame(
                    conflicting_segments
                )
            )

            # -------------------------------------------------
            # Send conflicting reuse.
            # -------------------------------------------------

            conflicting_response = (
                send_mllp_frame(
                    conflicting_frame,
                    host=MIRTH_HOST,
                    port=MIRTH_ORM_PORT,
                    timeout=15.0,
                )
            )

            conflicting_ack = (
                remove_mllp_frame(
                    conflicting_response
                )
            )

            (
                conflicting_ack_code,
                conflicting_ack_control_id,
            ) = parse_ack(
                conflicting_ack
            )

            # Conflicting reuse must be rejected.
            assert (
                conflicting_ack_code
                == "AR"
            )

            assert (
                conflicting_ack_control_id
                == expected["control_id"]
            )

            # -------------------------------------------------
            # Canonical transaction must still exist under the
            # same transaction_id.
            # -------------------------------------------------

            after_transaction = (
                run_interop_db_sql(
                    f"""
SELECT
    transaction_id,
    canonical_payload_sha256,
    receipt_count
FROM audit.interface_transactions
WHERE sending_application = 'EHR'
  AND sending_facility = 'INTEROPLAB'
  AND message_control_id =
      '{expected["control_id"]}';
""".strip()
                )
            )

            after_fields = (
                after_transaction.split("|")
            )

            assert (
                int(after_fields[0])
                == transaction_id
            )

            # The original canonical payload must not change.
            assert (
                after_fields[1]
                == canonical_hash
            )

            # The conflicting receipt is still observable.
            assert after_fields[2] == "2"

            # -------------------------------------------------
            # Canonical business order must remain unchanged.
            # -------------------------------------------------

            after_order = run_interop_db_sql(
                f"""
SELECT
    patient_identifier,
    placer_order_number,
    filler_order_number,
    accession_number,
    procedure_code,
    procedure_text
FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};
""".strip()
            )

            after_order_fields = (
                after_order.split("|")
            )

            assert (
                after_order_fields
                == canonical_order_fields
            )

            assert (
                after_order_fields[0]
                == expected["patient_id"]
            )

            assert (
                after_order_fields[0]
                != conflicting_patient
            )

            # Still exactly one canonical business order.
            orm_count = run_interop_db_sql(
                f"""
SELECT count(*)
FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};
""".strip()
            )

            assert orm_count == "1"

        finally:
            if transaction_id is not None:
                run_interop_db_sql(
                    f"""
DELETE FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};

DELETE FROM audit.interface_messages
WHERE transaction_id =
      {transaction_id};

DELETE FROM audit.interface_transactions
WHERE transaction_id =
      {transaction_id};
""".strip()
                )