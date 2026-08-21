from dataclasses import dataclass

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelMove,
)


PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"
MOVE_DESTINATION = "INTEROPLAB"

STUDY_INSTANCE_UID = (
    "1.2.826.0.1.3680043.8.498."
    "87268366001692831770011579401804357263"
)


@dataclass
class MoveResult:
    final_status: int
    completed: int
    failed: int
    warnings: int


def move_study(
    study_instance_uid: str,
    *,
    move_destination: str = MOVE_DESTINATION,
    calling_ae_title: str = CALLING_AE_TITLE,
) -> MoveResult:
    ae = AE(
        ae_title=calling_ae_title
    )

    ae.add_requested_context(
        StudyRootQueryRetrieveInformationModelMove
    )

    association = ae.associate(
        PACS_HOST,
        PACS_PORT,
        ae_title=CALLED_AE_TITLE,
    )

    if not association.is_established:
        raise RuntimeError(
            "DICOM association failed."
        )

    query = Dataset()
    query.QueryRetrieveLevel = "STUDY"
    query.StudyInstanceUID = study_instance_uid

    final_status = None
    completed = 0
    failed = 0
    warnings = 0

    try:
        responses = association.send_c_move(
            query,
            move_destination,
            StudyRootQueryRetrieveInformationModelMove,
        )

        for status, identifier in responses:
            if status is None:
                raise RuntimeError(
                    "C-MOVE returned no status response."
                )

            if "Status" not in status:
                raise RuntimeError(
                    "C-MOVE returned an invalid "
                    "status response."
                )

            final_status = int(
                status.Status
            )

            completed = int(
                getattr(
                    status,
                    "NumberOfCompletedSuboperations",
                    completed,
                )
            )

            failed = int(
                getattr(
                    status,
                    "NumberOfFailedSuboperations",
                    failed,
                )
            )

            warnings = int(
                getattr(
                    status,
                    "NumberOfWarningSuboperations",
                    warnings,
                )
            )

    finally:
        if association.is_established:
            association.release()

    if final_status is None:
        raise RuntimeError(
            "C-MOVE completed without a final status."
        )

    return MoveResult(
        final_status=final_status,
        completed=completed,
        failed=failed,
        warnings=warnings,
    )


def main() -> None:
    print()
    print("DICOM C-MOVE STUDY RETRIEVE")
    print("---------------------------")
    print(f"Calling AE:       {CALLING_AE_TITLE}")
    print(f"Called AE:        {CALLED_AE_TITLE}")
    print(f"Move destination: {MOVE_DESTINATION}")
    print(f"Study UID:        {STUDY_INSTANCE_UID}")
    print()

    try:
        result = move_study(
            STUDY_INSTANCE_UID
        )

    except RuntimeError as exc:
        print(f"C-MOVE FAILED: {exc}")
        print("OVERALL: FAIL")
        raise SystemExit(1)

    print(
        f"Final status: 0x{result.final_status:04X}"
    )
    print(f"Completed:    {result.completed}")
    print(f"Failed:       {result.failed}")
    print(f"Warnings:     {result.warnings}")
    print()

    if (
        result.final_status != 0x0000
        or result.completed != 1
        or result.failed != 0
        or result.warnings != 0
    ):
        print("OVERALL: FAIL")
        raise SystemExit(1)

    print("OVERALL: PASS")


if __name__ == "__main__":
    main()