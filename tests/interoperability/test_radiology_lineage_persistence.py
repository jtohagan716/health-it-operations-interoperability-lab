from pathlib import Path

import pydicom
import pytest

from scripts.radiology.persist_lineage import (
    delete_radiology_workflow,
    persist_radiology_lineage,
    run_interop_db_sql,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "orm-rad-workflow-000001.hl7"
)

DICOM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "dicom-rad-workflow-000001.dcm"
)

ORU_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "oru-rad-workflow-000001.hl7"
)


def create_conflicting_dicom(
    tmp_path: Path,
) -> Path:
    """
    Create a structurally valid DICOM study that reuses the
    same accession and Study Instance UID but changes the
    patient identity.

    This simulates conflicting reuse of an existing
    canonical radiology workflow identity.
    """

    dataset = pydicom.dcmread(
        DICOM_FIXTURE
    )

    dataset.PatientID = "RADPAT999999"

    output_path = (
        tmp_path
        / "dicom-conflicting-patient.dcm"
    )

    dataset.save_as(
        output_path,
        enforce_file_format=True,
    )

    return output_path


def test_radiology_lineage_persistence_is_idempotent():
    workflow_id = None

    try:
        first_id = persist_radiology_lineage(
            ORM_FIXTURE,
            DICOM_FIXTURE,
            ORU_FIXTURE,
        )

        workflow_id = first_id

        second_id = persist_radiology_lineage(
            ORM_FIXTURE,
            DICOM_FIXTURE,
            ORU_FIXTURE,
        )

        assert first_id == second_id

        row_count = run_interop_db_sql(
            f"""
SELECT COUNT(*)
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {first_id};
""".strip()
        )

        assert row_count == "1"

    finally:
        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )


def test_conflicting_radiology_identity_is_rejected(
    tmp_path: Path,
):
    workflow_id = None

    try:
        workflow_id = persist_radiology_lineage(
            ORM_FIXTURE,
            DICOM_FIXTURE,
            ORU_FIXTURE,
        )

        conflicting_dicom = (
            create_conflicting_dicom(
                tmp_path
            )
        )

        with pytest.raises(
            ValueError,
            match="Radiology patient identity mismatch",
        ):
            persist_radiology_lineage(
                ORM_FIXTURE,
                conflicting_dicom,
                ORU_FIXTURE,
            )

        canonical_patient = run_interop_db_sql(
            f"""
SELECT patient_identifier
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        assert canonical_patient == "RADPAT000001"

    finally:
        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )