from pathlib import Path

from pydicom import dcmread

from scripts.dicom.create_test_dicom import (
    SERIES_INSTANCE_UID,
    SOP_INSTANCE_UID,
    STUDY_INSTANCE_UID,
    create_test_dicom,
)


def fixture_identity(path: Path) -> tuple[str, str, str]:
    dataset = dcmread(
        path,
        stop_before_pixels=True,
    )

    return (
        str(dataset.StudyInstanceUID),
        str(dataset.SeriesInstanceUID),
        str(dataset.SOPInstanceUID),
    )


def test_consecutive_fixture_builds_preserve_identity(
    tmp_path: Path,
):
    first_path = tmp_path / "first.dcm"
    second_path = tmp_path / "second.dcm"

    create_test_dicom(first_path)
    create_test_dicom(second_path)

    expected_identity = (
        STUDY_INSTANCE_UID,
        SERIES_INSTANCE_UID,
        SOP_INSTANCE_UID,
    )

    assert fixture_identity(first_path) == expected_identity
    assert fixture_identity(second_path) == expected_identity


def test_file_meta_matches_dataset_sop_identity(
    tmp_path: Path,
):
    fixture_path = tmp_path / "fixture.dcm"
    create_test_dicom(fixture_path)

    dataset = dcmread(
        fixture_path,
        stop_before_pixels=True,
    )

    assert (
        str(dataset.file_meta.MediaStorageSOPInstanceUID)
        == str(dataset.SOPInstanceUID)
        == SOP_INSTANCE_UID
    )