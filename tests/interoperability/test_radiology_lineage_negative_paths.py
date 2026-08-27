from pathlib import Path

import pydicom
import pytest

from scripts.hl7.analyze_orm import analyze_orm
from scripts.radiology.lineage import (
    validate_order_to_dicom,
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


def create_wrong_accession_dicom(
    tmp_path: Path,
) -> Path:
    """
    Create a structurally valid DICOM study that preserves
    the expected patient identity but belongs to the wrong
    accession/order context.
    """

    dataset = pydicom.dcmread(
        DICOM_FIXTURE
    )

    dataset.AccessionNumber = "RAD999999"

    output_path = (
        tmp_path
        / "dicom-wrong-accession.dcm"
    )

    dataset.save_as(
        output_path,
        enforce_file_format=True,
    )

    return output_path


def test_wrong_accession_dicom_is_rejected(
    tmp_path: Path,
):
    orm = analyze_orm(
        ORM_FIXTURE
    )

    wrong_dicom_path = (
        create_wrong_accession_dicom(
            tmp_path
        )
    )

    dicom = pydicom.dcmread(
        wrong_dicom_path,
        stop_before_pixels=True,
    )

    # The DICOM artifact itself is still valid and readable.
    assert str(
        dicom.PatientID
    ) == "RADPAT000001"

    # Only the order/accession relationship was corrupted.
    assert str(
        dicom.AccessionNumber
    ) == "RAD999999"

    # Reject the clinical relationship even though the
    # underlying DICOM object is structurally valid.
    with pytest.raises(
        ValueError,
        match="Radiology accession mismatch",
    ):
        validate_order_to_dicom(
            orm,
            dicom,
        )