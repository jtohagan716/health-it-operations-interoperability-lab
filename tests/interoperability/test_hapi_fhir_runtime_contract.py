import os
import time
from uuid import uuid4

import pytest
import requests


HAPI_FHIR_BASE_URL = os.getenv(
    "HAPI_FHIR_BASE_URL",
    "http://localhost:8090/fhir",
).rstrip("/")

FHIR_HEADERS = {
    "Accept": "application/fhir+json",
}

FHIR_JSON_HEADERS = {
    "Accept": "application/fhir+json",
    "Content-Type": "application/fhir+json",
}

TIMEOUT_SECONDS = 30
READINESS_REQUEST_TIMEOUT_SECONDS = 10
HAPI_STARTUP_TIMEOUT_SECONDS = 240
READINESS_POLL_SECONDS = 5


@pytest.fixture(scope="module", autouse=True)
def hapi_fhir_is_ready():
    deadline = time.monotonic() + HAPI_STARTUP_TIMEOUT_SECONDS
    last_status = "No response received"

    while time.monotonic() < deadline:
        try:
            response = requests.get(
                f"{HAPI_FHIR_BASE_URL}/metadata",
                headers=FHIR_HEADERS,
                timeout=READINESS_REQUEST_TIMEOUT_SECONDS,
            )

            if response.status_code == 200:
                return

            last_status = (
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        except requests.RequestException as error:
            last_status = repr(error)

        time.sleep(READINESS_POLL_SECONDS)

    pytest.fail(
        "HAPI FHIR endpoint did not become ready within "
        f"{HAPI_STARTUP_TIMEOUT_SECONDS} seconds. "
        f"Last result: {last_status}"
    )


def test_hapi_r4_capability_statement_is_available():
    response = requests.get(
        f"{HAPI_FHIR_BASE_URL}/metadata",
        headers=FHIR_HEADERS,
        timeout=TIMEOUT_SECONDS,
    )

    assert response.status_code == 200, (
        f"HAPI metadata request failed: "
        f"HTTP {response.status_code}: {response.text}"
    )

    metadata = response.json()

    assert metadata["resourceType"] == "CapabilityStatement"
    assert metadata["fhirVersion"].startswith("4.")
    assert "json" in metadata.get("format", [])


def test_hapi_patient_create_read_and_identifier_search():
    identifier_system = (
        "https://health-it-operations-interoperability-lab.example/test"
    )
    identifier_value = f"HAPI-RUNTIME-{uuid4().hex}"

    patient_body = {
        "resourceType": "Patient",
        "identifier": [
            {
                "system": identifier_system,
                "value": identifier_value,
            }
        ],
        "name": [
            {
                "family": "HAPI",
                "given": ["Runtime"],
            }
        ],
        "gender": "unknown",
    }

    create_response = requests.post(
        f"{HAPI_FHIR_BASE_URL}/Patient",
        headers=FHIR_JSON_HEADERS,
        json=patient_body,
        timeout=TIMEOUT_SECONDS,
    )

    assert create_response.status_code == 201, (
        f"HAPI Patient create failed: "
        f"HTTP {create_response.status_code}: {create_response.text}"
    )

    created_patient = create_response.json()
    patient_id = created_patient.get("id")

    assert created_patient["resourceType"] == "Patient"
    assert patient_id
    assert created_patient["meta"]["versionId"] == "1"

    read_response = requests.get(
        f"{HAPI_FHIR_BASE_URL}/Patient/{patient_id}",
        headers=FHIR_HEADERS,
        timeout=TIMEOUT_SECONDS,
    )

    assert read_response.status_code == 200, (
        f"HAPI Patient read failed: "
        f"HTTP {read_response.status_code}: {read_response.text}"
    )

    returned_patient = read_response.json()

    assert returned_patient["resourceType"] == "Patient"
    assert returned_patient["id"] == patient_id
    assert returned_patient["name"][0]["family"] == "HAPI"
    assert returned_patient["name"][0]["given"] == ["Runtime"]

    search_response = requests.get(
        f"{HAPI_FHIR_BASE_URL}/Patient",
        params={
            "identifier": f"{identifier_system}|{identifier_value}",
        },
        headers=FHIR_HEADERS,
        timeout=TIMEOUT_SECONDS,
    )

    assert search_response.status_code == 200, (
        f"HAPI Patient search failed: "
        f"HTTP {search_response.status_code}: {search_response.text}"
    )

    search_bundle = search_response.json()
    entries = search_bundle.get("entry", [])

    assert search_bundle["resourceType"] == "Bundle"
    assert search_bundle["total"] == 1
    assert any(
        entry["resource"]["id"] == patient_id
        for entry in entries
    )