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
    "fixtures/dicom/interop-lab-test-image.dcm"
)


def main() -> None:
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
    print("DICOM C-STORE SEND")
    print("------------------")
    print(f"File:        {DICOM_FILE}")
    print(f"Calling AE:  {CALLING_AE_TITLE}")
    print(f"Called AE:   {CALLED_AE_TITLE}")
    print(f"Host:        {PACS_HOST}")
    print(f"Port:        {PACS_PORT}")
    print()
    print(f"Patient ID:  {dataset.PatientID}")
    print(f"Accession:   {dataset.AccessionNumber}")
    print(f"Study UID:   {dataset.StudyInstanceUID}")
    print(f"Series UID:  {dataset.SeriesInstanceUID}")
    print(f"SOP UID:     {dataset.SOPInstanceUID}")
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
        raise SystemExit(1)

    print("Association: ACCEPTED")

    status = association.send_c_store(
        dataset
    )

    end_time = perf_counter()

    duration_ms = (
        end_time - start_time
    ) * 1000.0

    if status is None:
        association.release()

        print("C-STORE:     NO RESPONSE")
        print("OVERALL:     FAIL")
        raise SystemExit(1)

    status_code = status.Status

    print(
        f"C-STORE:     0x{status_code:04X}"
    )

    print(
        f"Round-trip:  {duration_ms:.2f} ms"
    )

    association.release()

    if status_code != 0x0000:
        print("OVERALL:     FAIL")
        raise SystemExit(1)

    print("OVERALL:     PASS")


if __name__ == "__main__":
    main()