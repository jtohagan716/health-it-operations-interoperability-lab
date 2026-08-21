import requests

from scripts.fhir.auth_probe import require_fresh_access_token
from scripts.fhir.patient_helpers import (
    get_fhir_patient,
    load_hl7_patient,
)

FHIR_BASE_URL = "https://localhost:9300/apis/default/fhir"


def test_patient_identifier_search_actually_works():
    hl7_patient = load_hl7_patient()

    patient = get_fhir_patient(
        hl7_patient["identifier"]
    )

    assert patient["resourceType"] == "Patient"


def test_returned_patient_can_be_read_by_logical_id():
    hl7_patient = load_hl7_patient()

    patient = get_fhir_patient(
        hl7_patient["identifier"]
    )

    patient_id = patient["id"]

    access_token = require_fresh_access_token()

    response = requests.get(
        f"{FHIR_BASE_URL}/Patient/{patient_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/fhir+json",
        },
        verify=False,
        timeout=30,
    )

    assert response.status_code == 200, (
        f"FHIR Patient read failed: "
        f"HTTP {response.status_code}: {response.text}"
    )

    returned_patient = response.json()

    assert returned_patient["resourceType"] == "Patient"
    assert returned_patient["id"] == patient_id