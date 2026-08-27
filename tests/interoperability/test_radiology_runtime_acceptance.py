from pathlib import Path
import uuid

import pydicom
import requests

from pydicom.uid import generate_uid
from pynetdicom import AE

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
from scripts.radiology.orthanc_lineage_reconciliation import (
    reconcile_and_persist_radiology_workflow,
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

ORTHANC_BASE_URL = "http://127.0.0.1:8042"

ORTHANC_HOST = "127.0.0.1"
ORTHANC_DICOM_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"


def create_acceptance_case(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    dict[str, str],
]:
    """
    Create one completely isolated radiology case.

    The ORM, DICOM, and ORU all represent the same synthetic
    clinical imaging workflow.

    Runtime-generated identities protect persistent showcase
    data and make repeated executions deterministic.
    """

    suffix = uuid.uuid4().hex[:6].upper()

    orm_control_id = (
        f"RAD-ORM-ACC-{suffix}"
    )

    oru_control_id = (
        f"RAD-ORU-ACC-{suffix}"
    )

    patient_id = (
        f"RADAC{suffix}"
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
    # Create isolated ORM.
    # ---------------------------------------------------------

    orm_text = BASE_ORM_FIXTURE.read_text(
        encoding="ascii"
    )

    orm_text = orm_text.replace(
        "RAD-ORM-WORKFLOW-000001",
        orm_control_id,
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
        / "orm-radiology-acceptance.hl7"
    )

    orm_path.write_text(
        orm_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # Create isolated ORU.
    #
    # This result belongs to exactly the same patient,
    # order, and accession as the ORM.
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
        / "oru-radiology-acceptance.hl7"
    )

    oru_path.write_text(
        oru_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # Create isolated DICOM.
    # ---------------------------------------------------------

    dataset = pydicom.dcmread(
        BASE_DICOM_FIXTURE
    )

    dataset.PatientID = patient_id
    dataset.AccessionNumber = accession

    dataset.StudyInstanceUID = study_uid
    dataset.SeriesInstanceUID = series_uid
    dataset.SOPInstanceUID = sop_uid

    dataset.file_meta.MediaStorageSOPInstanceUID = (
        sop_uid
    )

    dicom_path = (
        tmp_path
        / "dicom-radiology-acceptance.dcm"
    )

    dataset.save_as(
        dicom_path,
        enforce_file_format=True,
    )

    expected = {
        "orm_control_id":
            orm_control_id,

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

        "series_uid":
            series_uid,

        "sop_uid":
            sop_uid,

        "modality":
            "DX",

        "report_status":
            "F",

        "impression":
            "No acute cardiopulmonary abnormality.",
    }

    return (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    )


def send_dicom_to_orthanc(
    dicom_path: Path,
) -> None:
    """
    Send one DICOM object to Orthanc through a real DICOM
    association using C-STORE.
    """

    dataset = pydicom.dcmread(
        dicom_path
    )

    ae = AE(
        ae_title=CALLING_AE_TITLE
    )

    ae.add_requested_context(
        dataset.SOPClassUID
    )

    association = ae.associate(
        ORTHANC_HOST,
        ORTHANC_DICOM_PORT,
        ae_title=CALLED_AE_TITLE,
    )

    assert association.is_established

    try:
        status = association.send_c_store(
            dataset
        )

        assert status is not None

        assert (
            status.Status
            == 0x0000
        )

    finally:
        association.release()


def find_orthanc_studies(
    patient_id: str,
) -> list[str]:
    """
    Find Orthanc study IDs for the unique acceptance patient.
    """

    response = requests.post(
        f"{ORTHANC_BASE_URL}/tools/find",
        json={
            "Level": "Study",
            "Query": {
                "PatientID": patient_id,
            },
        },
        timeout=15.0,
    )

    response.raise_for_status()

    return response.json()


def get_orthanc_study(
    orthanc_study_id: str,
) -> dict:
    """
    Retrieve one study from the live Orthanc REST API.
    """

    response = requests.get(
        (
            f"{ORTHANC_BASE_URL}"
            f"/studies/{orthanc_study_id}"
        ),
        timeout=15.0,
    )

    response.raise_for_status()

    return response.json()


def get_orthanc_series(
    orthanc_series_id: str,
) -> dict:
    """
    Retrieve one Orthanc series so modality can be validated
    at the DICOM level where it naturally belongs.
    """

    response = requests.get(
        (
            f"{ORTHANC_BASE_URL}"
            f"/series/{orthanc_series_id}"
        ),
        timeout=15.0,
    )

    response.raise_for_status()

    return response.json()


def delete_orthanc_studies(
    patient_id: str,
) -> None:
    """
    Delete only PACS studies belonging to this disposable
    acceptance-test patient.
    """

    study_ids = find_orthanc_studies(
        patient_id
    )

    for study_id in study_ids:
        response = requests.delete(
            (
                f"{ORTHANC_BASE_URL}"
                f"/studies/{study_id}"
            ),
            timeout=15.0,
        )

        response.raise_for_status()


def test_radiology_runtime_acceptance_end_to_end(
    tmp_path: Path,
):
    """
    End-to-end runtime radiology acceptance contract.

    One unique clinical imaging case must:

      1. enter Mirth as ORM^O01 over TCP/MLLP,
      2. receive an AA application acknowledgment,
      3. preserve MSH-10 acknowledgment correlation,
      4. persist canonical interface transaction state,
      5. persist normalized ORM business state,
      6. preserve patient/order/accession/procedure identity,
      7. generate a matching DICOM study,
      8. enter Orthanc using real DICOM C-STORE,
      9. preserve patient/accession/study/modality semantics,
     10. correlate with a matching final ORU report,
     11. persist complete ORM -> DICOM -> ORU lineage,
     12. reconcile that workflow against live Orthanc,
     13. persist RECONCILED PACS state,
     14. prove ORM and radiology workflow database records
         describe the same clinical case,
     15. clean up only state owned by this test execution.
    """

    transaction_id = None
    radiology_workflow_id = None
    orthanc_study_id = None

    (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    ) = create_acceptance_case(
        tmp_path
    )

    try:
        # =====================================================
        # PHASE 1
        # HL7 ORM -> Mirth -> ACK
        # =====================================================

        segments = load_hl7_fixture(
            orm_path
        )

        control_id = get_message_control_id(
            segments
        )

        assert (
            control_id
            == expected["orm_control_id"]
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
            == expected["orm_control_id"]
        )

        # =====================================================
        # PHASE 2
        # Verify interface transaction persistence.
        # =====================================================

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
      '{expected["orm_control_id"]}';
""".strip()
            )
        )

        transaction_fields = (
            transaction_output.split("|")
        )

        assert len(transaction_fields) == 6

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
            == expected["orm_control_id"]
        )

        assert (
            transaction_fields[4]
            == "1"
        )

        assert (
            transaction_fields[5]
            == "64"
        )

        # =====================================================
        # PHASE 3
        # Verify normalized ORM business state.
        # =====================================================

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

        orm_fields = (
            orm_output.split("|")
        )

        assert len(orm_fields) == 10

        assert (
            int(orm_fields[0])
            == transaction_id
        )

        assert (
            orm_fields[1]
            == expected["orm_control_id"]
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

        assert orm_fields[6] == "NW"
        assert orm_fields[7] == "SC"

        assert (
            orm_fields[8]
            == expected["procedure_code"]
        )

        assert (
            orm_fields[9]
            == expected["procedure_text"]
        )

        # =====================================================
        # PHASE 4
        # DICOM -> Orthanc using real C-STORE.
        # =====================================================

        send_dicom_to_orthanc(
            dicom_path
        )

        study_ids = find_orthanc_studies(
            expected["patient_id"]
        )

        assert len(study_ids) == 1

        orthanc_study_id = (
            study_ids[0]
        )

        study = get_orthanc_study(
            orthanc_study_id
        )

        study_tags = (
            study["MainDicomTags"]
        )

        patient_tags = (
            study["PatientMainDicomTags"]
        )

        assert (
            patient_tags["PatientID"]
            == expected["patient_id"]
        )

        assert (
            study_tags["AccessionNumber"]
            == expected["accession"]
        )

        assert (
            study_tags["StudyInstanceUID"]
            == expected["study_uid"]
        )

        assert (
            study_tags["StudyDescription"]
            == expected["procedure_text"]
        )

        # -----------------------------------------------------
        # Modality belongs naturally at the series level.
        # -----------------------------------------------------

        series_ids = study.get(
            "Series",
            [],
        )

        assert len(series_ids) == 1

        series = get_orthanc_series(
            series_ids[0]
        )

        series_tags = (
            series["MainDicomTags"]
        )

        assert (
            series_tags["Modality"]
            == expected["modality"]
        )

        # =====================================================
        # PHASE 5
        # ORM -> DICOM -> ORU lineage persistence.
        #
        # persist_radiology_lineage() itself performs the
        # semantic validation before inserting anything.
        # =====================================================

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

        # =====================================================
        # PHASE 6
        # Reconcile canonical workflow against live PACS and
        # persist the operational reconciliation state.
        # =====================================================

        reconciliation = (
            reconcile_and_persist_radiology_workflow(
                radiology_workflow_id,
                orm_path,
                dicom_path,
                oru_path,
            )
        )

        assert (
            reconciliation["passed"]
            is True
        )

        checks = reconciliation[
            "checks"
        ]

        assert (
            checks["patient_id_preserved"]
            is True
        )

        assert (
            checks["accession_number_preserved"]
            is True
        )

        assert (
            checks["study_uid_preserved"]
            is True
        )

        assert (
            checks["study_description_preserved"]
            is True
        )

        assert (
            checks["modality_preserved"]
            is True
        )

        # =====================================================
        # PHASE 7
        # Independently verify persisted radiology workflow
        # and PACS reconciliation state.
        #
        # We do not merely trust the function return value.
        # We query the actual durable database state.
        # =====================================================

        workflow_output = run_interop_db_sql(
            f"""
SELECT
    radiology_workflow_id,
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code,
    procedure_text,
    study_instance_uid,
    modality,
    oru_message_control_id,
    report_status,
    impression,
    lineage_status,
    orthanc_study_id,
    pacs_reconciliation_status,
    pacs_reconciliation_detail,
    CASE
        WHEN pacs_reconciled_at IS NOT NULL
        THEN 'SET'
        ELSE 'NULL'
    END
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {radiology_workflow_id};
""".strip()
        )

        workflow_fields = (
            workflow_output.split("|")
        )

        assert len(workflow_fields) == 16

        assert (
            int(workflow_fields[0])
            == radiology_workflow_id
        )

        assert (
            workflow_fields[1]
            == expected["patient_id"]
        )

        assert (
            workflow_fields[2]
            == expected["placer_order"]
        )

        assert (
            workflow_fields[3]
            == expected["accession"]
        )

        assert (
            workflow_fields[4]
            == expected["procedure_code"]
        )

        assert (
            workflow_fields[5]
            == expected["procedure_text"]
        )

        assert (
            workflow_fields[6]
            == expected["study_uid"]
        )

        assert (
            workflow_fields[7]
            == expected["modality"]
        )

        assert (
            workflow_fields[8]
            == expected["oru_control_id"]
        )

        assert (
            workflow_fields[9]
            == expected["report_status"]
        )

        assert (
            workflow_fields[10]
            == expected["impression"]
        )

        assert (
            workflow_fields[11]
            == "MATCHED"
        )

        assert (
            workflow_fields[12]
            == orthanc_study_id
        )

        assert (
            workflow_fields[13]
            == "RECONCILED"
        )

        assert (
            workflow_fields[14]
            == (
                "Live Orthanc PACS metadata matched "
                "the canonical radiology workflow."
            )
        )

        assert (
            workflow_fields[15]
            == "SET"
        )

        # =====================================================
        # PHASE 8
        # Cross-layer database lineage.
        #
        # This is deliberately independent of the earlier
        # assertions. We ask PostgreSQL to compare the Mirth
        # ORM business record with the persisted radiology
        # workflow.
        #
        # The integration succeeds only when BOTH database
        # representations describe the same clinical case.
        # =====================================================

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
    r.procedure_text
FROM audit.orm_orders AS o
JOIN audit.radiology_workflows AS r
  ON r.accession_number =
     o.accession_number
WHERE o.transaction_id =
      {transaction_id}
  AND r.radiology_workflow_id =
      {radiology_workflow_id};
""".strip()
        )

        linkage_fields = (
            linkage_output.split("|")
        )

        assert len(linkage_fields) == 10

        assert (
            linkage_fields[0]
            == linkage_fields[1]
            == expected["patient_id"]
        )

        assert (
            linkage_fields[2]
            == linkage_fields[3]
            == expected["placer_order"]
        )

        assert (
            linkage_fields[4]
            == linkage_fields[5]
            == expected["accession"]
        )

        assert (
            linkage_fields[6]
            == linkage_fields[7]
            == expected["procedure_code"]
        )

        assert (
            linkage_fields[8]
            == linkage_fields[9]
            == expected["procedure_text"]
        )

    finally:
        # =====================================================
        # CLEANUP
        #
        # Fundamental test-ownership rule:
        #
        #     tests may delete only data they created.
        #
        # Every identity used by this test was generated
        # specifically for this execution.
        # =====================================================

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

        delete_orthanc_studies(
            expected["patient_id"]
        )