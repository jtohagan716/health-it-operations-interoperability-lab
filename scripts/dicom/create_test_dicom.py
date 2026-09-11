from pathlib import Path
from datetime import datetime

import numpy as np
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
)


OUTPUT_PATH = Path(
    "fixtures/dicom/interop-lab-test-image.dcm"
)

STUDY_INSTANCE_UID = (
    "1.2.826.0.1.3680043.8.498."
    "87268366001692831770011579401804357263"
)

SERIES_INSTANCE_UID = (
    "1.2.826.0.1.3680043.8.498."
    "87268366001692831770011579401804357264"
)

SOP_INSTANCE_UID = (
    "1.2.826.0.1.3680043.8.498."
    "87268366001692831770011579401804357265"
)

def create_test_dicom(
    output_path: Path = OUTPUT_PATH,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_meta = Dataset()

    file_meta.MediaStorageSOPClassUID = (
        SecondaryCaptureImageStorage
    )

    sop_instance_uid = SOP_INSTANCE_UID

    file_meta.MediaStorageSOPInstanceUID = (
        sop_instance_uid
    )

    file_meta.TransferSyntaxUID = (
        ExplicitVRLittleEndian
    )

    now = datetime.now()

    dataset = FileDataset(
    str(output_path),
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )

    # --------------------------------------------------
    # Patient identity
    # --------------------------------------------------

    dataset.PatientName = "Interop^Patient"
    dataset.PatientID = "IMG000001"
    dataset.PatientBirthDate = "19800101"
    dataset.PatientSex = "O"

    # --------------------------------------------------
    # Study
    # --------------------------------------------------

    dataset.StudyInstanceUID = STUDY_INSTANCE_UID
    dataset.StudyDate = now.strftime("%Y%m%d")
    dataset.StudyTime = now.strftime("%H%M%S")

    dataset.AccessionNumber = "RAD000001"
    dataset.StudyID = "STUDY0001"
    dataset.StudyDescription = (
        "Interop Lab Synthetic Imaging Study"
    )

    # --------------------------------------------------
    # Series
    # --------------------------------------------------

    dataset.SeriesInstanceUID = SERIES_INSTANCE_UID
    dataset.SeriesNumber = "1"
    dataset.SeriesDescription = (
        "Synthetic QA Series"
    )

    dataset.Modality = "OT"

    # --------------------------------------------------
    # Instance
    # --------------------------------------------------

    dataset.SOPClassUID = (
        SecondaryCaptureImageStorage
    )

    dataset.SOPInstanceUID = (
        sop_instance_uid
    )

    dataset.InstanceNumber = "1"

    # --------------------------------------------------
    # Minimal synthetic pixel data
    # --------------------------------------------------

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
    output_path,
        enforce_file_format=True,
    )

    print()
    print("SYNTHETIC DICOM FIXTURE CREATED")
    print("-------------------------------")
    print(f"File:          {output_path}")
    print(f"Patient ID:    {dataset.PatientID}")
    print(f"Accession:     {dataset.AccessionNumber}")
    print(f"Modality:      {dataset.Modality}")
    print(f"Study UID:     {dataset.StudyInstanceUID}")
    print(f"Series UID:    {dataset.SeriesInstanceUID}")
    print(f"Instance UID:  {dataset.SOPInstanceUID}")

    return output_path


if __name__ == "__main__":
    create_test_dicom()