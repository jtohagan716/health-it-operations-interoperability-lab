from pathlib import Path
from time import perf_counter

import pydicom

from pynetdicom import AE
from pynetdicom.sop_class import (
    SecondaryCaptureImageStorage,
)


PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"

DICOM_FILE = Path(
    "fixtures/radiology/"
    "dicom-rad-workflow-000001.dcm"
)


def send_radiology_workflow_dicom() -> int:
    dataset = pydicom.dcmread(
        DICOM_FILE
    )

    ae = AE(
        ae_title=CALLING_AE_TITLE
    )

    ae.add_requested_context(
        SecondaryCaptureImageStorage
    )

    print()
    print("RADIOLOGY WORKFLOW DICOM C-STORE")
    print("--------------------------------")
    print(f"File:        {DICOM_FILE}")
    print(f"Calling AE:  {CALLING_AE_TITLE}")
    print(f"Called AE:   {CALLED_AE_TITLE}")
    print(f"Host:        {PACS_HOST}")
    print(f"Port:        {PACS_PORT}")
    print()
    print(f"Patient ID:  {dataset.PatientID}")
    print(f"Accession:   {dataset.AccessionNumber}")
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
    print()

    start_time = perf_counter()

    association = ae.associate(
        PACS_HOST,
        PACS_PORT,
        ae_title=CALLED_AE_TITLE,
    )

    if not association.is_established:
        print("Association: REJECTED / FAILED")
        print("OVERALL:     FAIL")
        raise RuntimeError(
            "DICOM association could not be established."
        )

    print("Association: ACCEPTED")

    status = association.send_c_store(
        dataset
    )

    duration_ms = (
        perf_counter() - start_time
    ) * 1000.0

    if status is None:
        association.release()

        print("C-STORE:     NO RESPONSE")
        print("OVERALL:     FAIL")

        raise RuntimeError(
            "DICOM C-STORE returned no response."
        )

    status_code = int(
        status.Status
    )

    print(
        f"C-STORE:     0x{status_code:04X}"
    )

    print(
        f"Round-trip:  "
        f"{duration_ms:.2f} ms"
    )

    association.release()

    if status_code != 0x0000:
        print("OVERALL:     FAIL")

        raise RuntimeError(
            "DICOM C-STORE failed with "
            f"status 0x{status_code:04X}."
        )

    print("OVERALL:     PASS")

    return status_code


def main() -> None:
    send_radiology_workflow_dicom()


if __name__ == "__main__":
    main()