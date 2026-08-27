from pathlib import Path

from scripts.radiology.orthanc_lineage_reconciliation import (
    reconcile_radiology_workflow_to_orthanc,
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


def test_radiology_workflow_matches_orthanc_runtime():
    result = reconcile_radiology_workflow_to_orthanc(
        ORM_FIXTURE,
        DICOM_FIXTURE,
        ORU_FIXTURE,
    )

    assert result["passed"] is True

    assert result["checks"] == {
        "patient_id_preserved": True,
        "accession_number_preserved": True,
        "study_uid_preserved": True,
        "study_description_preserved": True,
        "modality_preserved": True,
    }