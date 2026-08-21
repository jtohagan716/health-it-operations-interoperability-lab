from pathlib import Path
from datetime import datetime

import numpy as np
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)


OUTPUT_PATH = Path(
    "fixtures/dicom/interop-lab-nonrouting-test-image.dcm"
)


def create_nonrouting_test_dicom() -> Path:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_meta = Dataset()

    file_meta.MediaStorageSOPClassUID = (
        SecondaryCaptureImageStorage
    )

    sop_instance_uid = generate_uid()

    file_meta.MediaStorageSOPInstanceUID = (
        sop_instance_uid
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

    dataset.PatientName = "NoRoute^Patient"
    dataset.PatientID = "IMGNOROUTE001"
    dataset.PatientBirthDate = "19860101"
    dataset.PatientSex = "O"

    dataset.StudyInstanceUID = generate_uid()
    dataset.StudyDate = now.strftime("%Y%m%d")
    dataset.StudyTime = now.strftime("%H%M%S")

    dataset.AccessionNumber = "RADNOROUTE001"
    dataset.StudyID = "NOROUTESTUDY1"
    dataset.StudyDescription = (
        "Interop Lab No Route Study"
    )

    dataset.SeriesInstanceUID = generate_uid()
    dataset.SeriesNumber = "1"
    dataset.SeriesDescription = (
        "No Route QA Series"
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
    dataset.PhotometricInterpretation = "MONOCHROME2"
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
    print("NON-ROUTING DICOM FIXTURE CREATED")
    print("---------------------------------")
    print(f"File:          {OUTPUT_PATH}")
    print(f"Patient ID:    {dataset.PatientID}")
    print(f"Accession:     {dataset.AccessionNumber}")
    print(f"Study UID:     {dataset.StudyInstanceUID}")
    print(f"Series UID:    {dataset.SeriesInstanceUID}")
    print(f"SOP UID:       {dataset.SOPInstanceUID}")

    return OUTPUT_PATH


if __name__ == "__main__":
    create_nonrouting_test_dicom()