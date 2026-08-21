from pathlib import Path
from time import sleep, monotonic

import numpy as np

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

from pynetdicom import AE


PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"

RECEIVED_DIR = Path(
    "artifacts/dicom/received"
)

ROUTING_ACCESSION = "RADROUTE001"
NONROUTING_ACCESSION = "RADNOROUTE001"


def build_test_dataset(
    *,
    patient_id: str,
    accession_number: str,
) -> Dataset:
    """
    Build a unique synthetic DICOM Secondary Capture
    instance for routing-contract testing.
    """

    file_meta = FileMetaDataset()

    sop_instance_uid = generate_uid()

    file_meta.MediaStorageSOPClassUID = (
        SecondaryCaptureImageStorage
    )

    file_meta.MediaStorageSOPInstanceUID = (
        sop_instance_uid
    )

    file_meta.TransferSyntaxUID = (
        ExplicitVRLittleEndian
    )

    dataset = Dataset()

    dataset.file_meta = file_meta

    dataset.PatientName = "AutoRoute^Test"
    dataset.PatientID = patient_id
    dataset.PatientBirthDate = "19800101"
    dataset.PatientSex = "O"

    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()

    dataset.StudyDate = "20260821"
    dataset.StudyTime = "120000"

    dataset.AccessionNumber = accession_number

    dataset.StudyID = "AUTOROUTE1"

    dataset.StudyDescription = (
        "Automated PACS Routing Contract"
    )

    dataset.SeriesNumber = "1"

    dataset.SeriesDescription = (
        "Automated Routing QA Series"
    )

    dataset.Modality = "OT"

    dataset.SOPClassUID = (
        SecondaryCaptureImageStorage
    )

    dataset.SOPInstanceUID = (
        sop_instance_uid
    )

    dataset.InstanceNumber = "1"

    pixels = np.zeros(
        (64, 64),
        dtype=np.uint8,
    )

    dataset.Rows = 64
    dataset.Columns = 64
    dataset.SamplesPerPixel = 1

    dataset.PhotometricInterpretation = (
        "MONOCHROME2"
    )

    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0

    dataset.PixelData = (
        pixels.tobytes()
    )

    return dataset


def store_to_orthanc(
    dataset: Dataset,
) -> int:
    """
    Send the DICOM instance to Orthanc using C-STORE.
    """

    ae = AE(
        ae_title=CALLING_AE_TITLE
    )

    ae.add_requested_context(
        SecondaryCaptureImageStorage
    )

    association = ae.associate(
        PACS_HOST,
        PACS_PORT,
        ae_title=CALLED_AE_TITLE,
    )

    assert association.is_established, (
        "Could not establish DICOM association "
        "with Orthanc."
    )

    try:
        status = association.send_c_store(
            dataset
        )

        assert status is not None, (
            "C-STORE returned no status."
        )

        assert "Status" in status, (
            "C-STORE returned an invalid "
            "status response."
        )

        return int(
            status.Status
        )

    finally:
        if association.is_established:
            association.release()


def received_path(
    sop_instance_uid: str,
) -> Path:
    return (
        RECEIVED_DIR
        / f"{sop_instance_uid}.dcm"
    )


def wait_for_received_object(
    path: Path,
    *,
    timeout_seconds: float = 10.0,
) -> bool:
    """
    Wait for an automatically routed DICOM object
    to arrive at the downstream Storage SCP.
    """

    deadline = (
        monotonic()
        + timeout_seconds
    )

    while monotonic() < deadline:
        if path.exists():
            return True

        sleep(0.25)

    return False


def test_matching_accession_is_automatically_routed():
    dataset = build_test_dataset(
        patient_id="IMGROUTEAUTO001",
        accession_number=ROUTING_ACCESSION,
    )

    destination_file = received_path(
        str(dataset.SOPInstanceUID)
    )

    if destination_file.exists():
        destination_file.unlink()

    status_code = store_to_orthanc(
        dataset
    )

    assert status_code == 0x0000

    received = wait_for_received_object(
        destination_file
    )

    assert received is True, (
        "Matching DICOM instance was stored "
        "in Orthanc but was not automatically "
        "routed to INTEROPLAB."
    )

    assert destination_file.exists()


def test_nonmatching_accession_is_not_automatically_routed():
    dataset = build_test_dataset(
        patient_id="IMGNOROUTEAUTO001",
        accession_number=NONROUTING_ACCESSION,
    )

    destination_file = received_path(
        str(dataset.SOPInstanceUID)
    )

    if destination_file.exists():
        destination_file.unlink()

    status_code = store_to_orthanc(
        dataset
    )

    assert status_code == 0x0000

    sleep(3)

    assert destination_file.exists() is False, (
        "Nonmatching DICOM instance was "
        "unexpectedly routed to INTEROPLAB."
    )