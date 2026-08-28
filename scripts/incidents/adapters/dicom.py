from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pydicom
from pynetdicom import AE


@dataclass(frozen=True)
class DicomStoreResult:
    file_path: Path
    patient_id: str
    accession_number: str
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    status_code: int
    round_trip_ms: float

    @property
    def stored_successfully(self) -> bool:
        return self.status_code == 0x0000


def send_dicom_file(
    path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 4242,
    calling_ae_title: str = "INTEROPLAB",
    called_ae_title: str = "ORTHANC",
) -> DicomStoreResult:
    """
    Send one DICOM object using C-STORE and return
    structured transport/storage evidence.

    This adapter reports what happened at the DICOM
    association/C-STORE boundary. It does not prove
    that the stored study correlates correctly with
    an upstream clinical order.
    """

    dataset = pydicom.dcmread(
        path
    )

    ae = AE(
        ae_title=calling_ae_title
    )

    ae.add_requested_context(
        dataset.SOPClassUID
    )

    started = perf_counter()

    association = ae.associate(
        host,
        port,
        ae_title=called_ae_title,
    )

    if not association.is_established:
        raise RuntimeError(
            "DICOM association could not "
            f"be established with "
            f"{called_ae_title}@{host}:{port}."
        )

    try:
        status = association.send_c_store(
            dataset
        )

        round_trip_ms = (
            perf_counter() - started
        ) * 1000.0

        if status is None:
            raise RuntimeError(
                "DICOM C-STORE returned "
                "no response status."
            )

        status_code = int(
            status.Status
        )

    finally:
        association.release()

    return DicomStoreResult(
        file_path=path,
        patient_id=str(
            dataset.PatientID
        ),
        accession_number=str(
            dataset.AccessionNumber
        ),
        study_instance_uid=str(
            dataset.StudyInstanceUID
        ),
        series_instance_uid=str(
            dataset.SeriesInstanceUID
        ),
        sop_instance_uid=str(
            dataset.SOPInstanceUID
        ),
        status_code=status_code,
        round_trip_ms=round_trip_ms,
    )
