from scripts.fhir.auth_probe import (
    require_fresh_access_token,
    probe_patient_search,
)


PATIENT_IDENTIFIER = "LAB000001"


def test_fhir_patient_search_rejects_missing_token():
    response = probe_patient_search(
        PATIENT_IDENTIFIER,
        token=None,
    )

    assert response.status_code == 401, (
        "FHIR endpoint unexpectedly allowed an unauthenticated "
        f"Patient search: HTTP {response.status_code}"
    )


def test_fhir_patient_search_rejects_invalid_token():
    response = probe_patient_search(
        PATIENT_IDENTIFIER,
        token="invalid-test-token",
    )

    assert response.status_code == 401, (
        "FHIR endpoint unexpectedly accepted an invalid bearer "
        f"token: HTTP {response.status_code}"
    )


def test_fhir_patient_search_accepts_valid_token():
    access_token = require_fresh_access_token()

    response = probe_patient_search(
        PATIENT_IDENTIFIER,
        token=access_token,
    )

    assert response.status_code == 200, (
        "FHIR endpoint rejected a fresh valid bearer token: "
        f"HTTP {response.status_code}: {response.text}"
    )

    bundle = response.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle.get("total") == 1