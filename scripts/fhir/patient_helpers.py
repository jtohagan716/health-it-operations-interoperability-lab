from pathlib import Path
from time import perf_counter

import requests

from scripts.fhir.auth_probe import require_fresh_access_token


FHIR_BASE_URL = "https://localhost:9300/apis/default/fhir"

HL7_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "hl7"
    / "adt"
    / "adt-a04-lab000001.hl7"
)


def load_hl7_patient() -> dict:
    """
    Load patient identity information from the synthetic
    HL7 version 2 Admission, Discharge, Transfer (ADT) fixture.

    The Patient Identification (PID) segment is normalized
    into values that can be compared directly with a FHIR
    Patient resource.
    """

    message = HL7_FIXTURE.read_text(
        encoding="utf-8"
    )

    segments = {
        line.split("|", 1)[0]: line.split("|")
        for line in message.splitlines()
        if line.strip()
    }

    pid = segments["PID"]

    patient_id = pid[3].split("^")[0]

    name_components = pid[5].split("^")

    family_name = name_components[0]
    given_name = name_components[1]

    birth_date_raw = pid[7]

    birth_date = (
        f"{birth_date_raw[0:4]}-"
        f"{birth_date_raw[4:6]}-"
        f"{birth_date_raw[6:8]}"
    )

    hl7_gender = pid[8]

    gender_map = {
        "M": "male",
        "F": "female",
        "O": "other",
        "U": "unknown",
    }

    return {
        "identifier": patient_id,
        "family": family_name,
        "given": given_name,
        "birthDate": birth_date,
        "gender": gender_map.get(
            hl7_gender,
            "unknown",
        ),
    }


def get_fhir_patient_with_timing(
    identifier: str,
) -> tuple[dict, float]:
    """
    Search OpenEMR for a FHIR Patient by identifier and
    return both the Patient resource and measured API
    response duration in milliseconds.

    Timing covers the actual HTTP request/response operation.
    SMART on FHIR token prerequisite validation occurs before
    the timer starts so authentication-preparation time does
    not contaminate Patient search latency measurements.
    """

    access_token = require_fresh_access_token()

    start_time = perf_counter()

    response = requests.get(
        f"{FHIR_BASE_URL}/Patient",
        params={
            "identifier": identifier,
        },
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Accept": "application/fhir+json",
        },
        verify=False,
        timeout=30,
    )

    end_time = perf_counter()

    duration_ms = (
        end_time - start_time
    ) * 1000.0

    assert response.status_code == 200, (
        f"FHIR Patient search failed: "
        f"HTTP {response.status_code}: "
        f"{response.text}"
    )

    bundle = response.json()

    assert bundle["resourceType"] == "Bundle", (
        "FHIR Patient search did not return "
        "a Bundle."
    )

    assert bundle.get("total") == 1, (
        "FHIR Patient search expected exactly "
        f"one matching Patient but returned "
        f"total={bundle.get('total')}."
    )

    entries = bundle.get(
        "entry",
        [],
    )

    assert len(entries) == 1, (
        "FHIR Patient search expected exactly "
        f"one Bundle entry but found "
        f"{len(entries)}."
    )

    patient = entries[0]["resource"]

    assert (
        patient["resourceType"]
        == "Patient"
    ), (
        "FHIR search Bundle entry was not "
        "a Patient resource."
    )

    return patient, duration_ms


def get_fhir_patient(
    identifier: str,
) -> dict:
    """
    Backward-compatible Patient lookup.

    Existing tests and scripts expect this function to return
    only a Patient resource. The timed implementation is used
    internally while the duration is intentionally discarded.
    """

    patient, _duration_ms = (
        get_fhir_patient_with_timing(
            identifier
        )
    )

    return patient


def extract_fhir_identifier(
    patient: dict,
) -> str:
    """
    Return the first usable business identifier from a
    FHIR Patient resource.

    Note that Patient.identifier is different from the
    FHIR logical resource id stored in Patient.id.
    """

    identifiers = patient.get(
        "identifier",
        [],
    )

    for identifier in identifiers:
        value = identifier.get("value")

        if value:
            return value

    raise AssertionError(
        "FHIR Patient has no usable identifier."
    )