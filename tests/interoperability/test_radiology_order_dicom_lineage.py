from pathlib import Path

import pydicom

from scripts.hl7.analyze_orm import analyze_orm


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


def test_radiology_order_matches_dicom_study_identity():
    orm = analyze_orm(
        ORM_FIXTURE
    )

    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    assert orm["patient_id"] == str(
        dicom.PatientID
    )

    assert orm["accession_number"] == str(
        dicom.AccessionNumber
    )

    assert orm["procedure_text"] == str(
        dicom.StudyDescription
    )


def test_radiology_dicom_study_has_stable_identity():
    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    assert str(
        dicom.StudyInstanceUID
    ) == (
        "1.2.826.0.1.3680043.10.999.1001"
    )

    assert str(
        dicom.Modality
    ) == "DX"