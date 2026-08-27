from pathlib import Path
import tempfile
import uuid

import pydicom
from pydicom.uid import generate_uid

from scripts.hl7.send_mllp import (
    build_mllp_frame,
    get_message_control_id,
    load_hl7_fixture,
    parse_ack,
    remove_mllp_frame,
    send_mllp_frame,
)
from scripts.radiology.persist_lineage import (
    delete_radiology_workflow,
    persist_radiology_lineage,
    run_interop_db_sql,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_ORM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "orm-rad-workflow-000001.hl7"
)

BASE_DICOM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "dicom-rad-workflow-000001.dcm"
)

BASE_ORU_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "oru-rad-workflow-000001.hl7"
)

MIRTH_HOST = "localhost"
MIRTH_ORM_PORT = 6663


def create_isolated_runtime_workflow(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    dict[str, str],
]:
    """
    Create a disposable but internally consistent radiology
    workflow:

        ORM^O01
        DICOM study
        ORU^R01

    All transaction and clinical workflow identifiers are
    unique so repeated test runs cannot collide with
    documentation data or previous runs.
    """

    suffix = uuid.uuid4().hex[:10].upper()

    control_id = (
        f"RAD-ORM-LINK-{suffix}"
    )

    oru_control_id = (
        f"RAD-ORU-LINK-{suffix}"
    )

    patient_id = (
        f"RADLINK{suffix}"
    )

    placer_order = (
        f"RADORD{suffix}"
    )

    accession = (
        f"RAD{suffix}"
    )

    study_uid = generate_uid()
    series_uid = generate_uid()
    sop_uid = generate_uid()

    # ---------------------------------------------------------
    # ORM
    # ---------------------------------------------------------

    orm_text = BASE_ORM_FIXTURE.read_text(
        encoding="ascii"
    )

    orm_text = orm_text.replace(
        "RAD-ORM-WORKFLOW-000001",
        control_id,
    )

    orm_text = orm_text.replace(
        "RADPAT000001",
        patient_id,
    )

    orm_text = orm_text.replace(
        "RADORD000001",
        placer_order,
    )

    orm_text = orm_text.replace(
        "RAD000001",
        accession,
    )

    orm_path = (
        tmp_path
        / "orm-radiology-linkage.hl7"
    )

    orm_path.write_text(
        orm_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # ORU
    # ---------------------------------------------------------

    oru_text = BASE_ORU_FIXTURE.read_text(
        encoding="ascii"
    )

    oru_text = oru_text.replace(
        "RAD-ORU-WORKFLOW-000001",
        oru_control_id,
    )

    oru_text = oru_text.replace(
        "RADPAT000001",
        patient_id,
    )

    oru_text = oru_text.replace(
        "RADORD000001",
        placer_order,
    )

    oru_text = oru_text.replace(
        "RAD000001",
        accession,
    )

    oru_path = (
        tmp_path
        / "oru-radiology-linkage.hl7"
    )

    oru_path.write_text(
        oru_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # DICOM
    # ---------------------------------------------------------

    dicom = pydicom.dcmread(
        BASE_DICOM_FIXTURE
    )

    dicom.PatientID = patient_id
    dicom.AccessionNumber = accession

    dicom.StudyInstanceUID = (
        study_uid
    )

    dicom.SeriesInstanceUID = (
        series_uid
    )

    dicom.SOPInstanceUID = (
        sop_uid
    )

    dicom.file_meta.MediaStorageSOPInstanceUID = (
        sop_uid
    )

    dicom_path = (
        tmp_path
        / "dicom-radiology-linkage.dcm"
    )

    dicom.save_as(
        dicom_path,
        enforce_file_format=True,
    )

    expected = {
        "control_id":
            control_id,

        "oru_control_id":
            oru_control_id,

        "patient_id":
            patient_id,

        "placer_order":
            placer_order,

        "accession":
            accession,

        "procedure_code":
            "XRCH2",

        "procedure_text":
            "Chest X-ray 2 Views",

        "study_uid":
            study_uid,
    }

    return (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    )


def test_mirth_persisted_order_links_to_radiology_workflow():
    """
    Cross-layer runtime integration contract.

    Proves that the ORM order accepted by the live Mirth
    interface engine is the same clinical order represented
    by the normalized radiology workflow.

    Runtime path:

        ORM fixture
            -> MLLP
            -> Mirth
            -> interface_transactions
            -> orm_orders

        same ORM identity
            -> DICOM
            -> ORU
            -> radiology_workflows

    The order identity must agree across both persistence
    models.
    """

    transaction_id = None
    radiology_workflow_id = None

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)

        (
            orm_path,
            dicom_path,
            oru_path,
            expected,
        ) = create_isolated_runtime_workflow(
            tmp_path
        )

        try:
            # -------------------------------------------------
            # 1. Send the ORM through the real Mirth channel.
            # -------------------------------------------------

            segments = load_hl7_fixture(
                orm_path
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
            # 2. Retrieve the transaction Mirth actually
            #    persisted.
            # -------------------------------------------------

            transaction_output = (
                run_interop_db_sql(
                    f"""
SELECT
    transaction_id
FROM audit.interface_transactions
WHERE sending_application = 'EHR'
  AND sending_facility = 'INTEROPLAB'
  AND message_control_id =
      '{expected["control_id"]}';
""".strip()
                )
            )

            transaction_id = int(
                transaction_output
            )

            assert transaction_id > 0

            # -------------------------------------------------
            # 3. Verify normalized Mirth ORM business state.
            # -------------------------------------------------

            orm_output = run_interop_db_sql(
                f"""
SELECT
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code,
    procedure_text
FROM audit.orm_orders
WHERE transaction_id =
      {transaction_id};
""".strip()
            )

            orm_fields = orm_output.split("|")

            assert orm_fields == [
                expected["patient_id"],
                expected["placer_order"],
                expected["accession"],
                expected["procedure_code"],
                expected["procedure_text"],
            ]

            # -------------------------------------------------
            # 4. Build and persist the downstream normalized
            #    radiology workflow using the SAME ORM that
            #    traversed Mirth.
            # -------------------------------------------------

            radiology_workflow_id = (
                persist_radiology_lineage(
                    orm_path,
                    dicom_path,
                    oru_path,
                )
            )

            assert (
                radiology_workflow_id
                > 0
            )

            # -------------------------------------------------
            # 5. Compare the two independently persisted views
            #    of the clinical order.
            #
            # audit.orm_orders:
            #   "what Mirth accepted"
            #
            # audit.radiology_workflows:
            #   "what the complete imaging workflow represents"
            # -------------------------------------------------

            linkage_output = run_interop_db_sql(
                f"""
SELECT
    o.patient_identifier,
    r.patient_identifier,
    o.placer_order_number,
    r.placer_order_number,
    o.accession_number,
    r.accession_number,
    o.procedure_code,
    r.procedure_code,
    o.procedure_text,
    r.procedure_text,
    r.study_instance_uid,
    r.lineage_status,
    r.pacs_reconciliation_status
FROM audit.orm_orders o
JOIN audit.radiology_workflows r
  ON r.accession_number =
     o.accession_number
WHERE o.transaction_id =
      {transaction_id}
  AND r.radiology_workflow_id =
      {radiology_workflow_id};
""".strip()
            )

            fields = linkage_output.split("|")

            assert len(fields) == 13

            # Patient identity
            assert (
                fields[0]
                == fields[1]
                == expected["patient_id"]
            )

            # Placer order identity
            assert (
                fields[2]
                == fields[3]
                == expected["placer_order"]
            )

            # Accession identity
            assert (
                fields[4]
                == fields[5]
                == expected["accession"]
            )

            # Procedure code
            assert (
                fields[6]
                == fields[7]
                == expected["procedure_code"]
            )

            # Procedure text
            assert (
                fields[8]
                == fields[9]
                == expected["procedure_text"]
            )

            # DICOM Study identity is now attached to this
            # same normalized workflow.
            assert (
                fields[10]
                == expected["study_uid"]
            )

            # ORM + DICOM + ORU clinical relationship passed.
            assert (
                fields[11]
                == "MATCHED"
            )

            # This test has not yet performed the live
            # Orthanc reconciliation phase.
            assert (
                fields[12]
                == "PENDING"
            )

        finally:
            # -------------------------------------------------
            # Clean up only test-created state.
            # -------------------------------------------------

            if radiology_workflow_id is not None:
                delete_radiology_workflow(
                    radiology_workflow_id
                )

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