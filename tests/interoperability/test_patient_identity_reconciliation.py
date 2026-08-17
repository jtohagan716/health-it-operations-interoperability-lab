from pathlib import Path

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

def load_hl7_patient():
    message = HL7_FIXTURE.read_text(encoding="utf-8")

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
        "gender": gender_map.get(hl7_gender, "unknown"),
    }


def get_fhir_patient(identifier: str):
    access_token = require_fresh_access_token()

    response = requests.get(
        f"{FHIR_BASE_URL}/Patient",
        params={"identifier": identifier},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/fhir+json",
        },
        verify=False,
        timeout=30,
    )

    assert response.status_code == 200, (
        f"FHIR Patient search failed: "
        f"HTTP {response.status_code}: {response.text}"
    )

    bundle = response.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle.get("total") == 1

    entries = bundle.get("entry", [])
    assert len(entries) == 1

    patient = entries[0]["resource"]

    assert patient["resourceType"] == "Patient"

    return patient


def extract_fhir_identifier(patient):
    identifiers = patient.get("identifier", [])

    for identifier in identifiers:
        value = identifier.get("value")
        if value:
            return value

    raise AssertionError("FHIR Patient has no usable identifier.")


def test_openemr_fhir_matches_hl7_patient_identity():
    hl7_patient = load_hl7_patient()

    fhir_patient = get_fhir_patient(
        hl7_patient["identifier"]
    )

    fhir_identifier = extract_fhir_identifier(fhir_patient)

    official_names = [
        name
        for name in fhir_patient.get("name", [])
        if name.get("use") == "official"
    ]

    assert official_names, "FHIR Patient has no official name."

    fhir_name = official_names[0]

    assert fhir_identifier == hl7_patient["identifier"]
    assert fhir_name["family"] == hl7_patient["family"]
    assert fhir_name["given"][0] == hl7_patient["given"]
    assert fhir_patient["birthDate"] == hl7_patient["birthDate"]
    assert fhir_patient["gender"] == hl7_patient["gender"]