from pathlib import Path
import uuid

import pydicom
import requests

from pydicom.uid import generate_uid

from pynetdicom import AE

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


ORTHANC_BASE_URL = "http://127.0.0.1:8042"

PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"


def create_isolated_radiology_workflow(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    dict[str, str],
]:
    """
    Create a disposable ORM + DICOM + ORU workflow.

    Every identity that could collide with persistent
    demonstration data is unique for this test run.
    """

    suffix = uuid.uuid4().hex[:6].upper()

    patient_id = (
        f"RADPACS{suffix}"
    )

    placer_order = (
        f"RADORDPACS{suffix}"
    )

    accession = (
        f"RADPACS{suffix}"
    )

    orm_control_id = (
        f"RAD-ORM-PACS-{suffix}"
    )

    oru_control_id = (
        f"RAD-ORU-PACS-{suffix}"
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
        / "orm-pacs-reconciliation.hl7"
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
        / "oru-pacs-reconciliation.hl7"
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
        / "dicom-pacs-reconciliation.dcm"
    )

    dicom.save_as(
        dicom_path,
        enforce_file_format=True,
    )

    expected = {
        "patient_id":
            patient_id,

        "placer_order":
            placer_order,

        "accession":
            accession,

        "orm_control_id":
            orm_control_id,

        "oru_control_id":
            oru_control_id,

        "study_uid":
            study_uid,

        "procedure_code":
            "XRCH2",

        "procedure_text":
            "Chest X-ray 2 Views",

        "modality":
            "DX",
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
    Send the disposable test DICOM object to the live
    Orthanc PACS using a real DICOM C-STORE association.
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
        PACS_HOST,
        PACS_PORT,
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
        if association.is_established:
            association.release()


def find_orthanc_study_ids(
    patient_id: str,
) -> list[str]:
    """
    Return Orthanc study IDs belonging to the disposable
    test patient.
    """

    response = requests.post(
        f"{ORTHANC_BASE_URL}/tools/find",
        json={
            "Level": "Study",
            "Query": {
                "PatientID": patient_id,
            },
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def delete_orthanc_studies(
    patient_id: str,
) -> None:
    """
    Delete only studies associated with this test's unique
    synthetic patient identity.
    """

    study_ids = find_orthanc_study_ids(
        patient_id
    )

    for study_id in study_ids:
        response = requests.delete(
            (
                f"{ORTHANC_BASE_URL}"
                f"/studies/{study_id}"
            ),
            timeout=30,
        )

        response.raise_for_status()


def test_radiology_workflow_persists_and_reconciles_with_pacs(
    tmp_path: Path,
):
    """
    Live PACS reconciliation persistence contract.

    Proves that an isolated radiology workflow can:

      1. validate ORM + DICOM + ORU lineage,
      2. persist as MATCHED / PENDING,
      3. C-STORE the DICOM study into live Orthanc,
      4. reconcile expected identity against PACS state,
      5. persist MATCHED / RECONCILED,
      6. preserve the Orthanc study identifier,
      7. clean up only data created by this test.

    Persistent documentation data is never reused.
    """

    workflow_id = None
    expected = None

    (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    ) = create_isolated_radiology_workflow(
        tmp_path
    )

    try:
        # -----------------------------------------------------
        # 1. Persist the isolated canonical clinical workflow.
        # -----------------------------------------------------

        workflow_id = persist_radiology_lineage(
            orm_path,
            dicom_path,
            oru_path,
        )

        assert workflow_id > 0

        # -----------------------------------------------------
        # 2. Before PACS reconciliation, clinical lineage
        #    should be MATCHED but PACS state should be PENDING.
        # -----------------------------------------------------

        before = run_interop_db_sql(
            f"""
SELECT
    patient_identifier,
    accession_number,
    study_instance_uid,
    lineage_status,
    pacs_reconciliation_status
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        before_fields = before.split("|")

        assert (
            before_fields[0]
            == expected["patient_id"]
        )

        assert (
            before_fields[1]
            == expected["accession"]
        )

        assert (
            before_fields[2]
            == expected["study_uid"]
        )

        assert (
            before_fields[3]
            == "MATCHED"
        )

        assert (
            before_fields[4]
            == "PENDING"
        )

        # -----------------------------------------------------
        # 3. Send this test's DICOM study into live Orthanc.
        # -----------------------------------------------------

        send_dicom_to_orthanc(
            dicom_path
        )

        study_ids = find_orthanc_study_ids(
            expected["patient_id"]
        )

        assert len(study_ids) == 1

        expected_orthanc_study_id = (
            study_ids[0]
        )

        # -----------------------------------------------------
        # 4. Reconcile the persisted workflow against the
        #    actual state stored in Orthanc.
        # -----------------------------------------------------

        reconciliation = (
            reconcile_and_persist_radiology_workflow(
                workflow_id,
                orm_path,
                dicom_path,
                oru_path,
            )
        )

        assert (
            reconciliation["passed"]
            is True
        )

        assert reconciliation["checks"] == {
            "patient_id_preserved": True,
            "accession_number_preserved": True,
            "study_uid_preserved": True,
            "study_description_preserved": True,
            "modality_preserved": True,
        }

        # -----------------------------------------------------
        # 5. Verify durable success state in PostgreSQL.
        # -----------------------------------------------------

        after = run_interop_db_sql(
            f"""
SELECT
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code,
    procedure_text,
    study_instance_uid,
    modality,
    lineage_status,
    pacs_reconciliation_status,
    orthanc_study_id,
    CASE
        WHEN pacs_reconciled_at IS NOT NULL
        THEN 'TIMESTAMP_PRESENT'
        ELSE 'TIMESTAMP_MISSING'
    END
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        fields = after.split("|")

        assert (
            fields[0]
            == expected["patient_id"]
        )

        assert (
            fields[1]
            == expected["placer_order"]
        )

        assert (
            fields[2]
            == expected["accession"]
        )

        assert (
            fields[3]
            == expected["procedure_code"]
        )

        assert (
            fields[4]
            == expected["procedure_text"]
        )

        assert (
            fields[5]
            == expected["study_uid"]
        )

        assert (
            fields[6]
            == expected["modality"]
        )

        assert (
            fields[7]
            == "MATCHED"
        )

        assert (
            fields[8]
            == "RECONCILED"
        )

        assert (
            fields[9]
            == expected_orthanc_study_id
        )

        assert (
            fields[10]
            == "TIMESTAMP_PRESENT"
        )

    finally:
        # -----------------------------------------------------
        # Database cleanup.
        #
        # workflow_id belongs to a unique identity generated
        # by THIS test. It cannot refer to documentation row
        # 12 or another preexisting workflow.
        # -----------------------------------------------------

        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )

        # -----------------------------------------------------
        # PACS cleanup.
        #
        # Again, PatientID is unique to this test execution,
        # so the canonical RADPAT000001 study is untouched.
        # -----------------------------------------------------

        if expected is not None:
            delete_orthanc_studies(
                expected["patient_id"]
            )