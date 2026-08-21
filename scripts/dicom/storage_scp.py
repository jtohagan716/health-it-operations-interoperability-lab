from pathlib import Path

from pynetdicom import AE, evt
from pynetdicom.sop_class import (
    SecondaryCaptureImageStorage,
    Verification,
)


LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 11112
AE_TITLE = "INTEROPLAB"

OUTPUT_DIR = Path(
    "artifacts/dicom/received"
)


def handle_store(event):
    dataset = event.dataset

    dataset.file_meta = event.file_meta

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    sop_uid = str(
        dataset.SOPInstanceUID
    )

    output_path = (
        OUTPUT_DIR
        / f"{sop_uid}.dcm"
    )

    dataset.save_as(
        output_path,
        enforce_file_format=True,
    )

    print()
    print("DICOM C-STORE RECEIVED")
    print("----------------------")
    print(
        f"Patient ID:  "
        f"{getattr(dataset, 'PatientID', '')}"
    )
    print(
        f"Accession:   "
        f"{getattr(dataset, 'AccessionNumber', '')}"
    )
    print(
        f"Study UID:   "
        f"{getattr(dataset, 'StudyInstanceUID', '')}"
    )
    print(
        f"Series UID:  "
        f"{getattr(dataset, 'SeriesInstanceUID', '')}"
    )
    print(
        f"SOP UID:     "
        f"{sop_uid}"
    )
    print(
        f"Saved to:    "
        f"{output_path}"
    )

    return 0x0000


def main() -> None:
    ae = AE(
        ae_title=AE_TITLE
    )

    ae.add_supported_context(
        SecondaryCaptureImageStorage
    )

    ae.add_supported_context(
        Verification
    )

    handlers = [
        (
            evt.EVT_C_STORE,
            handle_store,
        )
    ]

    print()
    print("DICOM STORAGE SCP")
    print("-----------------")
    print(f"AE Title: {AE_TITLE}")
    print(f"Host:     {LISTEN_HOST}")
    print(f"Port:     {LISTEN_PORT}")
    print()
    print(
        "Waiting for incoming DICOM objects..."
    )

    ae.start_server(
        (
            LISTEN_HOST,
            LISTEN_PORT,
        ),
        block=True,
        evt_handlers=handlers,
    )


if __name__ == "__main__":
    main()