from time import perf_counter

import requests
import urllib3

from scripts.fhir.auth_probe import (
    require_fresh_access_token,
)
from scripts.fhir.patient_helpers import (
    get_fhir_patient,
    load_hl7_patient,
)


FHIR_BASE_URL = (
    "https://localhost:9300/apis/default/fhir"
)

REQUEST_TIMEOUT_SECONDS = 60


# Local OpenEMR uses a self-signed certificate.
# Suppress the warning only for this controlled lab.
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


def get_known_patient() -> dict:
    """
    Resolve the synthetic HL7 patient through the live
    OpenEMR FHIR Patient endpoint.

    This gives us a real FHIR logical Patient id to use
    for Observation and DiagnosticReport searches.
    """

    hl7_patient = load_hl7_patient()

    return get_fhir_patient(
        hl7_patient["identifier"]
    )


def authenticated_fhir_search(
    resource_type: str,
    params: dict,
) -> tuple[dict, float]:
    """
    Execute an authenticated FHIR search and return
    both the Bundle and HTTP response duration.

    SMART token prerequisite validation occurs before
    request timing begins.
    """

    access_token = require_fresh_access_token()

    start_time = perf_counter()

    response = requests.get(
        f"{FHIR_BASE_URL}/{resource_type}",
        params=params,
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Accept": "application/fhir+json",
        },
        verify=False,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    end_time = perf_counter()

    duration_ms = (
        end_time - start_time
    ) * 1000.0

    assert response.status_code == 200, (
        f"FHIR {resource_type} search failed: "
        f"HTTP {response.status_code}: "
        f"{response.text}"
    )

    payload = response.json()

    assert payload.get("resourceType") == "Bundle", (
        f"FHIR {resource_type} search expected "
        "a Bundle but received "
        f"{payload.get('resourceType')}."
    )

    return payload, duration_ms


def assert_bundle_entries_are_resource_type(
    bundle: dict,
    expected_resource_type: str,
) -> None:
    """
    A successful search may legitimately return zero
    resources.

    If resources are returned, every Bundle entry must
    contain the expected resource type.
    """

    for entry in bundle.get("entry", []):
        resource = entry.get(
            "resource",
            {},
        )

        assert (
            resource.get("resourceType")
            == expected_resource_type
        ), (
            "FHIR search Bundle contained "
            f"{resource.get('resourceType')} "
            f"when {expected_resource_type} "
            "was expected."
        )


def test_authenticated_observation_search_by_patient():
    patient = get_known_patient()

    patient_id = patient["id"]

    bundle, duration_ms = (
        authenticated_fhir_search(
            "Observation",
            {
                "patient": patient_id,
            },
        )
    )

    assert_bundle_entries_are_resource_type(
        bundle,
        "Observation",
    )

    assert duration_ms > 0


def test_authenticated_observation_search_by_patient_and_code():
    patient = get_known_patient()

    patient_id = patient["id"]

    bundle, duration_ms = (
        authenticated_fhir_search(
            "Observation",
            {
                "patient": patient_id,
                "code": "2345-7",
            },
        )
    )

    assert_bundle_entries_are_resource_type(
        bundle,
        "Observation",
    )

    assert duration_ms > 0


def test_authenticated_diagnostic_report_search_by_patient():
    patient = get_known_patient()

    patient_id = patient["id"]

    bundle, duration_ms = (
        authenticated_fhir_search(
            "DiagnosticReport",
            {
                "patient": patient_id,
            },
        )
    )

    assert_bundle_entries_are_resource_type(
        bundle,
        "DiagnosticReport",
    )

    assert duration_ms > 0


def test_authenticated_diagnostic_report_search_by_patient_and_code():
    patient = get_known_patient()

    patient_id = patient["id"]

    bundle, duration_ms = (
        authenticated_fhir_search(
            "DiagnosticReport",
            {
                "patient": patient_id,
                "code": "2345-7",
            },
        )
    )

    assert_bundle_entries_are_resource_type(
        bundle,
        "DiagnosticReport",
    )

    assert duration_ms > 0