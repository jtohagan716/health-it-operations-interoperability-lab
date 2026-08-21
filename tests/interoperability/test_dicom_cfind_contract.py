import pytest
from scripts.dicom.cfind_study_probe import (
    find_studies,
)


EXPECTED_PATIENT_ID = "IMG000001"
EXPECTED_ACCESSION = "RAD000001"

EXPECTED_STUDY_UID = (
    "1.2.826.0.1.3680043.8.498."
    "87268366001692831770011579401804357263"
)


def test_cfind_returns_expected_study():
    matches = find_studies(
        EXPECTED_PATIENT_ID,
        EXPECTED_ACCESSION,
    )

    assert len(matches) == 1

    study = matches[0]

    assert (
        str(study.PatientID)
        == EXPECTED_PATIENT_ID
    )

    assert (
        str(study.AccessionNumber)
        == EXPECTED_ACCESSION
    )


def test_cfind_preserves_study_identity():
    matches = find_studies(
        EXPECTED_PATIENT_ID,
        EXPECTED_ACCESSION,
    )

    assert len(matches) == 1

    study = matches[0]

    assert (
        str(study.StudyInstanceUID)
        == EXPECTED_STUDY_UID
    )


def test_cfind_returns_expected_study_metadata():
    matches = find_studies(
        EXPECTED_PATIENT_ID,
        EXPECTED_ACCESSION,
    )

    assert len(matches) == 1

    study = matches[0]

    assert (
        str(study.StudyDescription)
        == "Interop Lab Synthetic Imaging Study"
    )

    assert (
        str(study.ModalitiesInStudy)
        == "OT"
    )


def test_cfind_nonexistent_study_returns_zero_matches():
    matches = find_studies(
        "DOESNOTEXIST",
        "NOACCESSION",
    )

    assert matches == []
    
def test_cfind_rejects_unauthorized_calling_ae():
    with pytest.raises(
        RuntimeError,
        match=(
            "empty or invalid status response"
            "|DICOM association failed"
            "|Unexpected C-FIND status"
        ),
    ):
        find_studies(
            EXPECTED_PATIENT_ID,
            EXPECTED_ACCESSION,
            calling_ae_title="BADCLIENT",
        )