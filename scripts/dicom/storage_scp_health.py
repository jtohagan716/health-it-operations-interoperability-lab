import argparse

from pynetdicom import AE
from pynetdicom.sop_class import Verification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a DICOM Storage SCP with C-ECHO."
        )
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--called-ae", required=True)
    parser.add_argument(
        "--calling-ae",
        default="SCPHEALTH",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ae = AE(ae_title=args.calling_ae)
    ae.add_requested_context(Verification)

    association = ae.associate(
        args.host,
        args.port,
        ae_title=args.called_ae,
    )

    if not association.is_established:
        print("DICOM C-ECHO: ASSOCIATION FAILED")
        return 1

    try:
        status = association.send_c_echo()
    finally:
        association.release()

    status_code = getattr(status, "Status", None)
    if status_code != 0x0000:
        rendered = (
            "none"
            if status_code is None
            else f"0x{status_code:04X}"
        )
        print(f"DICOM C-ECHO: FAIL ({rendered})")
        return 1

    print("DICOM C-ECHO: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
