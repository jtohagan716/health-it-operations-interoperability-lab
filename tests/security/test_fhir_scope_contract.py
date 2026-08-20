from scripts.fhir.auth_probe import (
    load_token_data,
    require_fresh_access_token,
    fhir_get,
)


EXPECTED_SCOPES = {
    "fhirUser",
    "openid",
    "user/Encounter.rs",
    "user/Observation.rs",
    "user/Organization.rs",
    "user/Patient.rs",
    "user/Practitioner.rs",
}


def get_granted_scopes() -> set[str]:
    token_data = load_token_data()

    raw_scope = token_data.get("scope", "")

    return {
        scope
        for scope in raw_scope.split()
        if scope
    }


def test_expected_smart_scopes_are_granted():
    granted_scopes = get_granted_scopes()

    missing_scopes = EXPECTED_SCOPES - granted_scopes

    assert not missing_scopes, (
        "SMART authorization grant is missing expected scopes: "
        f"{sorted(missing_scopes)}"
    )


def test_patient_scope_supports_patient_search():
    token = require_fresh_access_token()

    response = fhir_get(
        "Patient",
        token=token,
        params={"identifier": "LAB000001"},
    )

    assert response.status_code == 200, (
        "Patient search failed despite granted "
        "user/Patient.rs scope: "
        f"HTTP {response.status_code}: {response.text}"
    )


def test_encounter_scope_supports_encounter_search():
    token = require_fresh_access_token()

    response = fhir_get(
        "Encounter",
        token=token,
        params={"_count": 1},
    )

    assert response.status_code == 200, (
        "Encounter search failed despite granted "
        "user/Encounter.rs scope: "
        f"HTTP {response.status_code}: {response.text}"
    )


def test_observation_scope_supports_observation_search():
    token = require_fresh_access_token()

    response = fhir_get(
        "Observation",
        token=token,
        params={"_count": 1},
    )

    assert response.status_code == 200, (
        "Observation search failed despite granted "
        "user/Observation.rs scope: "
        f"HTTP {response.status_code}: {response.text}"
    )


def test_organization_scope_is_constrained_by_ehr_policy():
    token = require_fresh_access_token()

    response = fhir_get(
        "Organization",
        token=token,
        params={"_count": 1},
    )

    assert response.status_code == 403, (
        "Expected Organization access to be denied by the "
        "configured EHR policy despite the granted SMART scope, "
        f"but received HTTP {response.status_code}: {response.text}"
    )

    payload = response.json()

    assert "policy" in payload.get("message", "").lower()


def test_practitioner_scope_is_constrained_by_ehr_policy():
    token = require_fresh_access_token()

    response = fhir_get(
        "Practitioner",
        token=token,
        params={"_count": 1},
    )

    assert response.status_code == 403, (
        "Expected Practitioner access to be denied by the "
        "configured EHR policy despite the granted SMART scope, "
        f"but received HTTP {response.status_code}: {response.text}"
    )

    payload = response.json()

    assert "policy" in payload.get("message", "").lower()