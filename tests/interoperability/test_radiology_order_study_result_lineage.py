from pathlib import Path

import pydicom

from scripts.hl7.analyze_orm import analyze_orm
from scripts.hl7.analyze_radiology_oru import (
    analyze_radiology_oru,
)

from scripts.radiology.lineage import (
    validate_full_radiology_lineage,
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


def test_radiology_patient_identity_is_preserved():
    orm = analyze_orm(
        ORM_FIXTURE
    )

    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        ORU_FIXTURE
    )

    assert (
        orm["patient_id"]
        == str(dicom.PatientID)
        == oru["patient_id"]
    )


def test_radiology_order_and_accession_identity_is_preserved():
    orm = analyze_orm(
        ORM_FIXTURE
    )

    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        ORU_FIXTURE
    )

    # EHR placer-order identity survives into the
    # resulting radiology report.
    assert (
        orm["orc_placer_order_number"]
        == oru["placer_order_number"]
    )

    # The filler order / accession number bridges
    # HL7 order, DICOM study, and HL7 result.
    assert (
        orm["accession_number"]
        == str(dicom.AccessionNumber)
        == oru["filler_order_number"]
    )


def test_radiology_procedure_identity_is_preserved():
    orm = analyze_orm(
        ORM_FIXTURE
    )

    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        ORU_FIXTURE
    )

    assert (
        orm["procedure_code"]
        == oru["service_code"]
    )

    assert (
        orm["procedure_text"]
        == str(dicom.StudyDescription)
        == oru["service_text"]
    )


def test_radiology_result_is_final_and_has_impression():
    oru = analyze_radiology_oru(
        ORU_FIXTURE
    )

    assert (
        oru["obr_result_status"]
        == "F"
    )

    assert (
        oru["obx_result_status"]
        == "F"
    )

    assert (
        oru["observation_code"]
        == "IMPRESSION"
    )

    assert (
        oru["observation_text"]
        == "Radiology Impression"
    )

    assert (
        oru["observation_value"]
        == (
            "No acute cardiopulmonary "
            "abnormality."
        )
    )


def test_radiology_dicom_study_has_expected_identity():
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


def test_full_radiology_lineage_contract_passes():
    orm = analyze_orm(
        ORM_FIXTURE
    )

    dicom = pydicom.dcmread(
        DICOM_FIXTURE,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        ORU_FIXTURE
    )

    lineage = validate_full_radiology_lineage(
        orm,
        dicom,
        oru,
    )

    assert lineage.patient_id == "RADPAT000001"
    assert lineage.placer_order_number == "RADORD000001"
    assert lineage.accession_number == "RAD000001"
    assert lineage.procedure_code == "XRCH2"
    assert lineage.procedure_text == "Chest X-ray 2 Views"
    assert lineage.study_instance_uid == (
        "1.2.826.0.1.3680043.10.999.1001"
    )
    assert lineage.modality == "DX"
    assert lineage.report_status == "F"
    assert lineage.impression == (
        "No acute cardiopulmonary abnormality."
    )