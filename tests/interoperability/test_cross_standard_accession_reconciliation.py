from copy import deepcopy
from pathlib import Path

import pydicom

from scripts.hl7.analyze_orm import analyze_orm
from scripts.hl7.analyze_radiology_oru import (
    analyze_radiology_oru,
)
from scripts.radiology.accession_reconciliation import (
    reconcile_accession_workflow,
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


def load_workflow():
    orm = analyze_orm(ORM_FIXTURE)

    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        ORU_FIXTURE
    )

    mwl = {
        "patient_identifier": orm["patient_id"],
        "requested_procedure_id": (
            orm["orc_placer_order_number"]
        ),
        "accession_number": orm["accession_number"],
        "procedure_code": orm["procedure_code"],
        "procedure_description": orm["procedure_text"],
        "modality": str(dicom.Modality),
        "projection_status": "PUBLISHED",
        "study_instance_uid": str(
            dicom.StudyInstanceUID
        ),
        "orthanc_worklist_id": "LAB-MWL-000001",
    }

    return orm, mwl, dicom, oru


def test_complete_workflow_passes():
    orm, mwl, dicom, oru = load_workflow()

    result = reconcile_accession_workflow(
        orm,
        mwl,
        dicom,
        oru,
    )

    assert result["status"] == "PASS"
    assert result["boundaries"] == {
        "orm_order": "PASS",
        "mwl_projection": "PASS",
        "pacs_study": "PASS",
        "final_oru": "PASS",
    }

    assert all(
        check["status"] == "PASS"
        for check in result["checks"]
    )


def test_wrong_pacs_accession_is_quarantined():
    orm, mwl, dicom, oru = load_workflow()
    dicom.AccessionNumber = "RAD999999"

    result = reconcile_accession_workflow(
        orm,
        mwl,
        dicom,
        oru,
    )

    assert result["status"] == "QUARANTINE"
    assert result["boundaries"]["pacs_study"] == "FAIL"

    failure = next(
        check
        for check in result["checks"]
        if check["boundary"] == "pacs_study"
        and check["field"] == "accession_number"
    )

    assert failure["expected"] == "RAD000001"
    assert failure["actual"] == "RAD999999"
    assert failure["status"] == "FAIL"


def test_missing_final_oru_is_incomplete():
    orm, mwl, dicom, _ = load_workflow()

    result = reconcile_accession_workflow(
        orm,
        mwl,
        dicom,
        None,
    )

    assert result["status"] == "INCOMPLETE"
    assert (
        result["boundaries"]["final_oru"]
        == "INCOMPLETE"
    )


def test_reconciliation_is_deterministic():
    orm, mwl, dicom, oru = load_workflow()

    first = reconcile_accession_workflow(
        deepcopy(orm),
        deepcopy(mwl),
        deepcopy(dicom),
        deepcopy(oru),
    )

    second = reconcile_accession_workflow(
        deepcopy(orm),
        deepcopy(mwl),
        deepcopy(dicom),
        deepcopy(oru),
    )

    assert first == second
