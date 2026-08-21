from pynetdicom import AE
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelFind,
)
from pydicom.dataset import Dataset


PACS_HOST = "127.0.0.1"
PACS_PORT = 4242

CALLING_AE_TITLE = "INTEROPLAB"
CALLED_AE_TITLE = "ORTHANC"


def find_studies(
    patient_id: str,
    accession_number: str,
    *,
    calling_ae_title: str = CALLING_AE_TITLE,
) -> list[Dataset]:
    """
    Query Orthanc at STUDY level using DICOM C-FIND.

    Returns all matching study-level response datasets.
    """

    ae = AE(
        ae_title=calling_ae_title
    )

    ae.add_requested_context(
        StudyRootQueryRetrieveInformationModelFind
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

    # Matching keys
    query.PatientID = patient_id
    query.AccessionNumber = accession_number

    # Return keys
    query.StudyInstanceUID = ""
    query.StudyDescription = ""
    query.StudyDate = ""
    query.ModalitiesInStudy = ""

    matches: list[Dataset] = []

    try:
        responses = association.send_c_find(
            query,
            StudyRootQueryRetrieveInformationModelFind,
        )

        for status, identifier in responses:
            if status is None:
                raise RuntimeError(
                    "C-FIND returned no status response."
                )

            if "Status" not in status:
                raise RuntimeError(
                    "C-FIND returned an empty or "
                    "invalid status response."
                )

            status_code = status.Status

            if status_code in (
                0xFF00,
                0xFF01,
            ):
                if identifier is None:
                    raise RuntimeError(
                        "C-FIND returned a pending "
                        "response without an identifier."
                    )

                matches.append(
                    identifier
                )

            elif status_code == 0x0000:
                # Final Success response
                continue

            else:
                raise RuntimeError(
                    "Unexpected C-FIND status: "
                    f"0x{status_code:04X}"
                )

    finally:
        if association.is_established:
            association.release()

    return matches


def main() -> None:
    patient_id = "IMG000001"
    accession_number = "RAD000001"

    print()
    print("DICOM C-FIND STUDY QUERY")
    print("------------------------")
    print(f"Patient ID: {patient_id}")
    print(f"Accession:  {accession_number}")
    print()

    try:
        matches = find_studies(
            patient_id,
            accession_number,
        )

    except RuntimeError as exc:
        print(
            f"C-FIND FAILED: {exc}"
        )
        print("OVERALL: FAIL")
        raise SystemExit(1)

    for match in matches:
        print("MATCH")

        print(
            "Patient ID:   "
            + str(
                getattr(
                    match,
                    "PatientID",
                    "",
                )
            )
        )

        print(
            "Accession:    "
            + str(
                getattr(
                    match,
                    "AccessionNumber",
                    "",
                )
            )
        )

        print(
            "Study UID:    "
            + str(
                getattr(
                    match,
                    "StudyInstanceUID",
                    "",
                )
            )
        )

        print(
            "Description:  "
            + str(
                getattr(
                    match,
                    "StudyDescription",
                    "",
                )
            )
        )

        print(
            "Study Date:   "
            + str(
                getattr(
                    match,
                    "StudyDate",
                    "",
                )
            )
        )

        print(
            "Modalities:   "
            + str(
                getattr(
                    match,
                    "ModalitiesInStudy",
                    "",
                )
            )
        )

        print()

    if len(matches) != 1:
        print(
            f"Expected exactly 1 match, "
            f"found {len(matches)}."
        )
        print("OVERALL: FAIL")
        raise SystemExit(1)

    match = matches[0]

    assert (
        str(match.PatientID)
        == patient_id
    )

    assert (
        str(match.AccessionNumber)
        == accession_number
    )

    print("C-FIND COMPLETE")
    print()
    print("OVERALL: PASS")


if __name__ == "__main__":
    main()