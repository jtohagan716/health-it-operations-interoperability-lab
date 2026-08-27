from pathlib import Path
from datetime import datetime

import numpy as np
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
)


OUTPUT_PATH = Path(
    "fixtures/radiology/dicom-rad-workflow-000001.dcm"
)

STUDY_INSTANCE_UID = (
    "1.2.826.0.1.3680043.10.999.1001"
)

SERIES_INSTANCE_UID = (
    "1.2.826.0.1.3680043.10.999.1001.1"
)

SOP_INSTANCE_UID = (
    "1.2.826.0.1.3680043.10.999.1001.1.1"
)


def create_radiology_workflow_dicom() -> Path:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_meta = Dataset()

    file_meta.MediaStorageSOPClassUID = (
        SecondaryCaptureImageStorage
    )

    file_meta.MediaStorageSOPInstanceUID = (
        SOP_INSTANCE_UID
    )

    file_meta.TransferSyntaxUID = (
        ExplicitVRLittleEndian
    )

    now = datetime.now()

    dataset = FileDataset(
        str(OUTPUT_PATH),
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )

    # Patient identity
    dataset.PatientName = "Testpatient^Avery"
    dataset.PatientID = "RADPAT000001"
    dataset.PatientBirthDate = "19800115"
    dataset.PatientSex = "M"

    # Study / order linkage
    dataset.StudyInstanceUID = (
        STUDY_INSTANCE_UID
    )

    dataset.StudyDate = now.strftime(
        "%Y%m%d"
    )

    dataset.StudyTime = now.strftime(
        "%H%M%S"
    )

    dataset.AccessionNumber = "RAD000001"

    dataset.StudyID = "RADSTUDY000001"

    dataset.StudyDescription = (
        "Chest X-ray 2 Views"
    )

    # Series
    dataset.SeriesInstanceUID = (
        SERIES_INSTANCE_UID
    )

    dataset.SeriesNumber = "1"

    dataset.SeriesDescription = (
        "Chest X-ray 2 Views"
    )

    # Modality
    dataset.Modality = "DX"

    # SOP identity
    dataset.SOPClassUID = (
        SecondaryCaptureImageStorage
    )

    dataset.SOPInstanceUID = (
        SOP_INSTANCE_UID
    )

    dataset.InstanceNumber = "1"

    # Minimal synthetic pixel data
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
    dataset.PixelData = pixels.tobytes()

    dataset.save_as(
        OUTPUT_PATH,
        enforce_file_format=True,
    )

    print()
    print("RADIOLOGY WORKFLOW DICOM CREATED")
    print("--------------------------------")
    print(f"File:        {OUTPUT_PATH}")
    print(f"Patient ID:  {dataset.PatientID}")
    print(
        f"Accession:   "
        f"{dataset.AccessionNumber}"
    )
    print(
        f"Study UID:   "
        f"{dataset.StudyInstanceUID}"
    )
    print(
        f"Series UID:  "
        f"{dataset.SeriesInstanceUID}"
    )
    print(
        f"SOP UID:     "
        f"{dataset.SOPInstanceUID}"
    )
    print(f"Modality:    {dataset.Modality}")

    return OUTPUT_PATH


if __name__ == "__main__":
    create_radiology_workflow_dicom()