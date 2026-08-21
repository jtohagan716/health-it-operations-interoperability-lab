from pathlib import Path

import pydicom

from scripts.dicom.cmove_study import (
    STUDY_INSTANCE_UID,
    move_study,
)


RECEIVED_DIR = Path(
    "artifacts/dicom/received"
)

EXPECTED_PATIENT_ID = "IMG000001"
EXPECTED_ACCESSION = "RAD000001"

EXPECTED_SERIES_UID = (
    "1.2.826.0.1.3680043.8.498."
    "41876962539834885805896333248367079466"
)

EXPECTED_SOP_UID = (
    "1.2.826.0.1.3680043.8.498."
    "11894887390651100331373701350258425061"
)


def newest_received_dicom() -> Path:
    files = list(
        RECEIVED_DIR.glob("*.dcm")
    )

    assert files, (
        "No retrieved DICOM files were found."
    )

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def test_cmove_completes_successfully():
    result = move_study(
        STUDY_INSTANCE_UID
    )

    assert result.final_status == 0x0000
    assert result.completed == 1
    assert result.failed == 0
    assert result.warnings == 0


def test_cmove_retrieved_object_preserves_patient_identity():
    result = move_study(
        STUDY_INSTANCE_UID
    )

    assert result.final_status == 0x0000

    path = newest_received_dicom()

    dataset = pydicom.dcmread(
        path
    )

    assert (
        str(dataset.PatientID)
        == EXPECTED_PATIENT_ID
    )

    assert (
        str(dataset.AccessionNumber)
        == EXPECTED_ACCESSION
    )


def test_cmove_retrieved_object_preserves_dicom_hierarchy():
    result = move_study(
        STUDY_INSTANCE_UID
    )

    assert result.final_status == 0x0000

    path = newest_received_dicom()

    dataset = pydicom.dcmread(
        path
    )

    assert (
        str(dataset.StudyInstanceUID)
        == STUDY_INSTANCE_UID
    )

    assert (
        str(dataset.SeriesInstanceUID)
        == EXPECTED_SERIES_UID
    )

    assert (
        str(dataset.SOPInstanceUID)
        == EXPECTED_SOP_UID
    )


def test_cmove_unknown_study_is_rejected_without_delivery():
    unknown_study_uid = (
        "1.2.826.0.1.3680043.8.498."
        "99999999999999999999999999999999999999"
    )

    files_before = {
        path.name: path.stat().st_mtime_ns
        for path in RECEIVED_DIR.glob("*.dcm")
    }

    result = move_study(
        unknown_study_uid
    )

    files_after = {
        path.name: path.stat().st_mtime_ns
        for path in RECEIVED_DIR.glob("*.dcm")
    }

    assert result.final_status == 0xC000
    assert result.completed == 0
    assert result.failed == 0
    assert result.warnings == 0

    assert files_after == files_before, (
        "Unknown-study C-MOVE unexpectedly "
        "created or modified a received DICOM object."
    )

def test_cmove_valid_study_fails_when_destination_unavailable():
    files_before = {
        path.name: path.stat().st_mtime_ns
        for path in RECEIVED_DIR.glob("*.dcm")
    }

    result = move_study(
        STUDY_INSTANCE_UID,
        move_destination="UNAVAILABLE",
    )

    files_after = {
        path.name: path.stat().st_mtime_ns
        for path in RECEIVED_DIR.glob("*.dcm")
    }

    assert result.final_status == 0xC000
    assert result.completed == 0
    assert result.failed == 0
    assert result.warnings == 0

    assert files_after == files_before, (
        "Unavailable-destination C-MOVE unexpectedly "
        "created or modified a received DICOM object."
    )