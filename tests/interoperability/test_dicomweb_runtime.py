from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

from scripts.dicom.dicomweb_client import (
    DicomWebClient,
    dicom_json_value,
    reconcile,
)


def build_unique_dataset(path: Path) -> FileDataset:
    file_meta = Dataset()
    sop_uid = generate_uid()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = FileDataset(
        str(path), {}, file_meta=file_meta, preamble=b"\0" * 128
    )
    suffix = sop_uid.split(".")[-1][-8:]
    dataset.PatientName = "DICOMweb^Runtime"
    dataset.PatientID = f"DWEB{suffix}"
    dataset.PatientBirthDate = "19800101"
    dataset.PatientSex = "O"
    dataset.StudyInstanceUID = generate_uid()
    dataset.StudyDate = "20260910"
    dataset.StudyTime = "230000"
    dataset.AccessionNumber = f"DWEBACC{suffix}"
    dataset.StudyID = f"DWEB{suffix}"
    dataset.StudyDescription = "DICOMweb Round Trip"
    dataset.SeriesInstanceUID = generate_uid()
    dataset.SeriesNumber = "1"
    dataset.SeriesDescription = "DICOMweb Runtime Series"
    dataset.Modality = "OT"
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = sop_uid
    dataset.InstanceNumber = "1"
    pixels = np.zeros((16, 16), dtype=np.uint8)
    dataset.Rows = 16
    dataset.Columns = 16
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelData = pixels.tobytes()
    dataset.save_as(path, enforce_file_format=True)
    return dataset


def test_stow_qido_wado_round_trip(tmp_path):
    source_path = tmp_path / "dicomweb-runtime.dcm"
    source = build_unique_dataset(source_path)
    client = DicomWebClient()

    stored = client.store(source_path)
    assert stored["status_code"] in (200, 202)

    studies = client.query_studies(
        study_instance_uid=str(source.StudyInstanceUID)
    )
    assert len(studies) == 1
    assert dicom_json_value(studies[0], "00100020") == source.PatientID
    assert dicom_json_value(studies[0], "00080050") == source.AccessionNumber
    assert dicom_json_value(studies[0], "0020000D") == source.StudyInstanceUID

    payload = client.retrieve_instance(
        study_instance_uid=str(source.StudyInstanceUID),
        series_instance_uid=str(source.SeriesInstanceUID),
        sop_instance_uid=str(source.SOPInstanceUID),
    )
    retrieved_path = tmp_path / "retrieved.dcm"
    retrieved_path.write_bytes(payload)
    from pydicom import dcmread

    retrieved = dcmread(retrieved_path)
    checks = reconcile(source, retrieved)
    assert all(checks.values()), checks
    assert retrieved.PixelData == source.PixelData
