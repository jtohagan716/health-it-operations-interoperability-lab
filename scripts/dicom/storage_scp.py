import argparse
import os
from pathlib import Path

from pynetdicom import AE, evt
from pynetdicom.sop_class import (
    SecondaryCaptureImageStorage,
    Verification,
)


DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 11112
DEFAULT_AE_TITLE = "INTEROPLAB"
DEFAULT_OUTPUT_DIR = "artifacts/dicom/received"


def environment_default(name: str, fallback: str) -> str:
    return os.getenv(name, fallback)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the InteropLab DICOM Storage SCP."
        )
    )
    parser.add_argument(
        "--host",
        default=environment_default(
            "DICOM_SCP_HOST",
            DEFAULT_LISTEN_HOST,
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(
            environment_default(
                "DICOM_SCP_PORT",
                str(DEFAULT_LISTEN_PORT),
            )
        ),
    )
    parser.add_argument(
        "--ae-title",
        default=environment_default(
            "DICOM_SCP_AE_TITLE",
            DEFAULT_AE_TITLE,
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            environment_default(
                "DICOM_SCP_OUTPUT_DIR",
                DEFAULT_OUTPUT_DIR,
            )
        ),
    )
    return parser.parse_args()


def build_store_handler(output_dir: Path):
    def handle_store(event):
        dataset = event.dataset
        dataset.file_meta = event.file_meta

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        sop_uid = str(
            getattr(dataset, "SOPInstanceUID", "")
        ).strip()

        if not sop_uid:
            print(
                "DICOM C-STORE REJECTED: "
                "missing SOP Instance UID",
                flush=True,
            )
            return 0xC210

        output_path = output_dir / f"{sop_uid}.dcm"

        try:
            dataset.save_as(
                output_path,
                enforce_file_format=True,
            )
        except Exception as exc:
            print(
                "DICOM C-STORE FAILED: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return 0xA700

        print(
            "DICOM C-STORE RECEIVED "
            f"patient_id={getattr(dataset, 'PatientID', '')} "
            f"accession={getattr(dataset, 'AccessionNumber', '')} "
            f"study_uid={getattr(dataset, 'StudyInstanceUID', '')} "
            f"series_uid={getattr(dataset, 'SeriesInstanceUID', '')} "
            f"sop_uid={sop_uid} "
            f"saved_to={output_path}",
            flush=True,
        )

        return 0x0000

    return handle_store


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ae = AE(ae_title=args.ae_title)
    ae.add_supported_context(
        SecondaryCaptureImageStorage
    )
    ae.add_supported_context(Verification)

    handlers = [
        (
            evt.EVT_C_STORE,
            build_store_handler(args.output_dir),
        )
    ]

    print("DICOM STORAGE SCP", flush=True)
    print(f"AE Title: {args.ae_title}", flush=True)
    print(f"Host:     {args.host}", flush=True)
    print(f"Port:     {args.port}", flush=True)
    print(f"Output:   {args.output_dir}", flush=True)
    print(
        "Waiting for incoming DICOM objects...",
        flush=True,
    )

    ae.start_server(
        (args.host, args.port),
        block=True,
        evt_handlers=handlers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
