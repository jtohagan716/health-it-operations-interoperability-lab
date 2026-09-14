import argparse

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pynetdicom import AE
from pynetdicom.sop_class import (
    ModalityWorklistInformationFind,
)


PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "CT_MODALITY"
CALLED_AE_TITLE = "ORTHANC"


def find_worklists(
    accession_number: str,
    *,
    modality: str = "CT",
    calling_ae_title: str = CALLING_AE_TITLE,
    host: str = PACS_HOST,
    port: int = PACS_PORT,
    called_ae_title: str = CALLED_AE_TITLE,
) -> list[Dataset]:
    """
    Query Orthanc using the DICOM Modality Worklist
    Information Model FIND service.

    Returns all matching worklist response datasets.
    """

    ae = AE(
        ae_title=calling_ae_title
    )

    ae.add_requested_context(
        ModalityWorklistInformationFind
    )

    association = ae.associate(
        host,
        port,
        ae_title=called_ae_title,
    )

    if not association.is_established:
        raise RuntimeError(
            "DICOM MWL association failed."
        )

    query = Dataset()

    # Top-level matching and return keys.
    query.AccessionNumber = accession_number
    query.PatientID = ""
    query.PatientName = ""
    query.PatientBirthDate = ""
    query.PatientSex = ""
    query.ReferringPhysicianName = ""
    query.RequestedProcedureID = ""
    query.RequestedProcedureDescription = ""
    query.StudyInstanceUID = ""

    # Scheduled Procedure Step matching and return keys.
    scheduled_step = Dataset()

    scheduled_step.Modality = modality
    scheduled_step.ScheduledStationAETitle = ""
    scheduled_step.ScheduledProcedureStepStartDate = ""
    scheduled_step.ScheduledProcedureStepStartTime = ""
    scheduled_step.ScheduledProcedureStepID = ""
    scheduled_step.ScheduledProcedureStepDescription = ""

    query.ScheduledProcedureStepSequence = Sequence(
        [scheduled_step]
    )

    matches: list[Dataset] = []

    try:
        responses = association.send_c_find(
            query,
            ModalityWorklistInformationFind,
        )

        for status, identifier in responses:
            if status is None:
                raise RuntimeError(
                    "MWL C-FIND returned no status response."
                )

            if "Status" not in status:
                raise RuntimeError(
                    "MWL C-FIND returned an empty or "
                    "invalid status response."
                )

            status_code = int(
                status.Status
            )

            if status_code in (
                0xFF00,
                0xFF01,
            ):
                if identifier is None:
                    raise RuntimeError(
                        "MWL C-FIND returned a pending "
                        "response without an identifier."
                    )

                matches.append(
                    identifier
                )

            elif status_code == 0x0000:
                continue

            else:
                raise RuntimeError(
                    "Unexpected MWL C-FIND status: "
                    f"0x{status_code:04X}"
                )

    finally:
        if association.is_established:
            association.release()

    return matches


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Query Orthanc for a DICOM modality "
            "worklist item."
        )
    )

    parser.add_argument(
        "--accession",
        required=True,
    )

    parser.add_argument(
        "--modality",
        default="CT",
    )

    parser.add_argument(
        "--calling-ae",
        default=CALLING_AE_TITLE,
    )

    args = parser.parse_args()

    try:
        matches = find_worklists(
            args.accession,
            modality=args.modality,
            calling_ae_title=args.calling_ae,
        )

    except RuntimeError as exc:
        print()
        print(f"MWL C-FIND FAILED: {exc}")
        print("OVERALL: FAIL")
        raise SystemExit(1)

    print()
    print("DICOM MODALITY WORKLIST C-FIND")
    print("------------------------------")
    print(f"Accession: {args.accession}")
    print(f"Modality:  {args.modality}")
    print(f"Matches:   {len(matches)}")
    print()

    for match in matches:
        scheduled_step = (
            match.ScheduledProcedureStepSequence[0]
        )

        print(
            "Patient ID:     "
            f"{getattr(match, 'PatientID', '')}"
        )
        print(
            "Patient Name:   "
            f"{getattr(match, 'PatientName', '')}"
        )
        print(
            "Accession:      "
            f"{getattr(match, 'AccessionNumber', '')}"
        )
        print(
            "Procedure ID:   "
            f"{getattr(match, 'RequestedProcedureID', '')}"
        )
        print(
            "Study UID:      "
            f"{getattr(match, 'StudyInstanceUID', '')}"
        )
        print(
            "Station AE:     "
            f"{getattr(scheduled_step, 'ScheduledStationAETitle', '')}"
        )
        print(
            "Modality:       "
            f"{getattr(scheduled_step, 'Modality', '')}"
        )
        print(
            "Scheduled Date: "
            f"{getattr(scheduled_step, 'ScheduledProcedureStepStartDate', '')}"
        )
        print(
            "Scheduled Time: "
            f"{getattr(scheduled_step, 'ScheduledProcedureStepStartTime', '')}"
        )
        print(
            "Step ID:        "
            f"{getattr(scheduled_step, 'ScheduledProcedureStepID', '')}"
        )
        print()

    if len(matches) != 1:
        print(
            "Expected exactly one matching worklist."
        )
        print("OVERALL: FAIL")
        raise SystemExit(1)

    print("OVERALL: PASS")


if __name__ == "__main__":
    main()
