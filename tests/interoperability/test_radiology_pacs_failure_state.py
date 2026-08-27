from pathlib import Path
import uuid

import pydicom
from pydicom.uid import generate_uid

from scripts.radiology.persist_lineage import (
    delete_radiology_workflow,
    persist_radiology_lineage,
    run_interop_db_sql,
)
from scripts.radiology.orthanc_lineage_reconciliation import (
    persist_pacs_reconciliation,
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


def create_isolated_radiology_workflow(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, str]]:
    """
    Create a disposable but internally consistent
    ORM + DICOM + ORU workflow.

    The generated workflow uses unique clinical and DICOM
    identities so this test cannot collide with or modify
    the persistent documentation workflow.
    """

    suffix = uuid.uuid4().hex[:8].upper()

    patient_id = (
        f"RADFAIL{suffix}"
    )

    placer_order_number = (
        f"RADORDFAIL{suffix}"
    )

    accession_number = (
        f"ACCFAIL{suffix}"
    )

    oru_control_id = (
        f"RAD-ORU-FAIL-{suffix}"
    )

    study_instance_uid = generate_uid()

    # ---------------------------------------------------------
    # Create isolated ORM
    # ---------------------------------------------------------

    orm_text = BASE_ORM_FIXTURE.read_text(
        encoding="ascii"
    )

    orm_text = orm_text.replace(
        "RADPAT000001",
        patient_id,
    )

    orm_text = orm_text.replace(
        "RADORD000001",
        placer_order_number,
    )

    orm_text = orm_text.replace(
        "RAD000001",
        accession_number,
    )

    orm_path = (
        tmp_path
        / "orm-isolated-failure.hl7"
    )

    orm_path.write_text(
        orm_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # Create isolated ORU
    # ---------------------------------------------------------

    oru_text = BASE_ORU_FIXTURE.read_text(
        encoding="ascii"
    )

    oru_text = oru_text.replace(
        "RADPAT000001",
        patient_id,
    )

    oru_text = oru_text.replace(
        "RADORD000001",
        placer_order_number,
    )

    oru_text = oru_text.replace(
        "RAD000001",
        accession_number,
    )

    oru_text = oru_text.replace(
        "RAD-ORU-WORKFLOW-000001",
        oru_control_id,
    )

    oru_path = (
        tmp_path
        / "oru-isolated-failure.hl7"
    )

    oru_path.write_text(
        oru_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # Create isolated DICOM
    # ---------------------------------------------------------

    dicom = pydicom.dcmread(
        BASE_DICOM_FIXTURE
    )

    dicom.PatientID = patient_id
    dicom.AccessionNumber = accession_number
    dicom.StudyInstanceUID = study_instance_uid

    dicom_path = (
        tmp_path
        / "dicom-isolated-failure.dcm"
    )

    dicom.save_as(
        dicom_path,
        enforce_file_format=True,
    )

    expected = {
        "patient_id":
            patient_id,

        "placer_order_number":
            placer_order_number,

        "accession_number":
            accession_number,

        "oru_control_id":
            oru_control_id,

        "study_instance_uid":
            study_instance_uid,
    }

    return (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    )


def test_failed_pacs_reconciliation_is_persisted(
    tmp_path: Path,
):
    """
    Controlled PACS failure-state test.

    Important:

    The live Orthanc PACS is NOT modified.

    This test creates a disposable canonical clinical
    workflow and injects a simulated PACS reconciliation
    failure.

    Expected state transition:

        MATCHED / PENDING

                ->

        MATCHED / FAILED

    The clinical lineage remains valid because the ORM,
    DICOM source, and ORU still agree.

    Only downstream PACS reconciliation is considered
    failed.
    """

    workflow_id = None

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
        # Establish valid canonical clinical lineage.
        # -----------------------------------------------------

        workflow_id = persist_radiology_lineage(
            orm_path,
            dicom_path,
            oru_path,
        )

        assert workflow_id > 0

        # -----------------------------------------------------
        # Verify initial state.
        # -----------------------------------------------------

        before = run_interop_db_sql(
            f"""
SELECT
    patient_identifier,
    accession_number,
    lineage_status,
    pacs_reconciliation_status,
    COALESCE(
        pacs_reconciliation_detail,
        ''
    )
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
            == expected["accession_number"]
        )

        assert (
            before_fields[2]
            == "MATCHED"
        )

        assert (
            before_fields[3]
            == "PENDING"
        )

        # -----------------------------------------------------
        # Inject a controlled PACS mismatch.
        #
        # We are simulating an observed downstream study
        # whose accession identity does not agree with the
        # canonical workflow.
        # -----------------------------------------------------

        simulated_failure = {
            "orthanc_study": {
                "ID":
                    "SIMULATED-WRONG-STUDY"
            },

            "checks": {
                "patient_id_preserved":
                    True,

                "accession_number_preserved":
                    False,

                "study_uid_preserved":
                    True,

                "study_description_preserved":
                    True,

                "modality_preserved":
                    True,
            },

            "passed":
                False,
        }

        persist_pacs_reconciliation(
            workflow_id,
            simulated_failure,
        )

        # -----------------------------------------------------
        # Verify durable failure state.
        # -----------------------------------------------------

        after = run_interop_db_sql(
            f"""
SELECT
    patient_identifier,
    accession_number,
    lineage_status,
    pacs_reconciliation_status,
    orthanc_study_id,
    pacs_reconciliation_detail,
    CASE
        WHEN pacs_reconciled_at IS NULL
        THEN 'NO_SUCCESS_TIMESTAMP'
        ELSE 'UNEXPECTED_TIMESTAMP'
    END
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        after_fields = after.split("|")

        # Clinical identity must remain unchanged.
        assert (
            after_fields[0]
            == expected["patient_id"]
        )

        assert (
            after_fields[1]
            == expected["accession_number"]
        )

        # Clinical lineage remains valid.
        assert (
            after_fields[2]
            == "MATCHED"
        )

        # PACS operational state is independently failed.
        assert (
            after_fields[3]
            == "FAILED"
        )

        assert (
            after_fields[4]
            == "SIMULATED-WRONG-STUDY"
        )

        # Failure reason must be actionable.
        assert (
            "accession_number_preserved"
            in after_fields[5]
        )

        # A failed attempt must not masquerade as a
        # successful reconciliation timestamp.
        assert (
            after_fields[6]
            == "NO_SUCCESS_TIMESTAMP"
        )

    finally:
        # -----------------------------------------------------
        # Remove only this disposable database workflow.
        #
        # The saved documentation row and live Orthanc study
        # are never touched.
        # -----------------------------------------------------

        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )