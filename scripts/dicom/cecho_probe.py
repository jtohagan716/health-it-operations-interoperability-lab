from time import perf_counter

from pynetdicom import AE
from pynetdicom.sop_class import Verification


PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"


def main() -> None:
    ae = AE(
        ae_title=CALLING_AE_TITLE
    )

    ae.add_requested_context(
        Verification
    )

    print()
    print("DICOM C-ECHO CONNECTIVITY PROBE")
    print("-------------------------------")
    print(f"Calling AE:  {CALLING_AE_TITLE}")
    print(f"Called AE:   {CALLED_AE_TITLE}")
    print(f"Host:        {PACS_HOST}")
    print(f"Port:        {PACS_PORT}")
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

    status = association.send_c_echo()

    end_time = perf_counter()

    duration_ms = (
        end_time - start_time
    ) * 1000.0

    if status is None:
        association.release()

        print("C-ECHO:      NO RESPONSE")
        print("OVERALL:     FAIL")
        raise SystemExit(1)

    status_code = status.Status

    print(f"C-ECHO:      0x{status_code:04X}")
    print(f"Round-trip:  {duration_ms:.2f} ms")

    association.release()

    if status_code != 0x0000:
        print("OVERALL:     FAIL")
        raise SystemExit(1)

    print("OVERALL:     PASS")


if __name__ == "__main__":
    main()