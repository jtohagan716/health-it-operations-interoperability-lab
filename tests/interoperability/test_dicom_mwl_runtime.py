import json
from collections.abc import Iterator
from urllib.request import Request, urlopen

import pytest

from scripts.dicom.mwl_cfind_probe import (
    find_worklists,
)


ORTHANC_URL = "http://localhost:8042"

ACCESSION = "MWLRUNTIME000001"
PATIENT_ID = "MWLPATIENT000001"
PATIENT_NAME = "RUNTIME^WORKLIST"
PROCEDURE_ID = "MWLREQ000002"
PROCEDURE_DESCRIPTION = "CT CHEST WITHOUT CONTRAST"
STUDY_UID = (
    "1.2.826.0.1.3680043.10.5432."
    "202609120001"
)
SCHEDULED_DATE = "20260912"
SCHEDULED_TIME = "100000"
SCHEDULED_STEP_ID = "MWLSPS000002"
STATION_AE = "CT_MODALITY"
MODALITY = "CT"


def orthanc_request(
    method: str,
    path: str,
    payload: dict | None = None,
) -> object:
    body = None

    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(
            payload
        ).encode("utf-8")

        headers["Content-Type"] = (
            "application/json"
        )

    request = Request(
        f"{ORTHANC_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    with urlopen(
        request,
        timeout=10,
    ) as response:
        response_body = response.read()

    if not response_body:
        return None

    return json.loads(
        response_body.decode("utf-8")
    )


def delete_matching_worklists() -> None:
    worklists = orthanc_request(
        "GET",
        "/worklists/?format=Full",
    )

    assert isinstance(
        worklists,
        list,
    )

    for worklist in worklists:
        accession_tag = (
            worklist
            .get("Tags", {})
            .get("0008,0050", {})
        )

        if accession_tag.get("Value") == ACCESSION:
            orthanc_request(
                "DELETE",
                f"/worklists/{worklist['ID']}",
            )


@pytest.fixture(
    scope="module",
    autouse=True,
)
def deterministic_worklist() -> Iterator[None]:
    delete_matching_worklists()

    payload = {
        "Tags": {
            "PatientID": PATIENT_ID,
            "PatientName": PATIENT_NAME,
            "PatientBirthDate": "19800101",
            "PatientSex": "O",
            "AccessionNumber": ACCESSION,
            "StudyInstanceUID": STUDY_UID,
            "RequestedProcedureID": (
                PROCEDURE_ID
            ),
            "RequestedProcedureDescription": (
                PROCEDURE_DESCRIPTION
            ),
            "ReferringPhysicianName": (
                "PROVIDER^ORDERING"
            ),
            "ScheduledProcedureStepSequence": [
                {
                    "ScheduledStationAETitle": (
                        STATION_AE
                    ),
                    "ScheduledProcedureStepStartDate": (
                        SCHEDULED_DATE
                    ),
                    "ScheduledProcedureStepStartTime": (
                        SCHEDULED_TIME
                    ),
                    "Modality": MODALITY,
                    "ScheduledProcedureStepID": (
                        SCHEDULED_STEP_ID
                    ),
                    "ScheduledProcedureStepDescription": (
                        PROCEDURE_DESCRIPTION
                    ),
                }
            ],
        }
    }

    created = orthanc_request(
        "POST",
        "/worklists/create",
        payload,
    )

    assert isinstance(
        created,
        dict,
    )

    assert created.get("ID")

    try:
        yield

    finally:
        delete_matching_worklists()


def test_mwl_cfind_returns_expected_identity():
    matches = find_worklists(
        ACCESSION,
        modality=MODALITY,
    )

    assert len(matches) == 1

    worklist = matches[0]
    scheduled_step = (
        worklist
        .ScheduledProcedureStepSequence[0]
    )

    assert str(
        worklist.PatientID
    ) == PATIENT_ID

    assert str(
        worklist.PatientName
    ) == PATIENT_NAME

    assert str(
        worklist.AccessionNumber
    ) == ACCESSION

    assert str(
        worklist.RequestedProcedureID
    ) == PROCEDURE_ID

    assert str(
        worklist.StudyInstanceUID
    ) == STUDY_UID

    assert str(
        scheduled_step.Modality
    ) == MODALITY

    assert str(
        scheduled_step.ScheduledStationAETitle
    ) == STATION_AE

    assert str(
        scheduled_step.ScheduledProcedureStepStartDate
    ) == SCHEDULED_DATE

    assert str(
        scheduled_step.ScheduledProcedureStepStartTime
    ) == SCHEDULED_TIME

    assert str(
        scheduled_step.ScheduledProcedureStepID
    ) == SCHEDULED_STEP_ID


def test_mwl_cfind_unknown_accession_returns_no_matches():
    matches = find_worklists(
        "MWLDOESNOTEXIST",
        modality=MODALITY,
    )

    assert matches == []


def test_mwl_cfind_rejects_unauthorized_calling_ae():
    with pytest.raises(
        RuntimeError,
        match=(
            "empty or invalid status response"
            "|DICOM MWL association failed"
            "|Unexpected MWL C-FIND status"
        ),
    ):
        find_worklists(
            ACCESSION,
            modality=MODALITY,
            calling_ae_title="BADCLIENT",
        )