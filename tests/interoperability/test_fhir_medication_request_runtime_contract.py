from time import perf_counter

import requests
import urllib3
import pytest

from scripts.fhir.auth_probe import require_fresh_access_token
from scripts.fhir.patient_helpers import (
    get_fhir_patient,
    load_hl7_patient,
)


FHIR_BASE_URL = "https://localhost:9300/apis/default/fhir"
REQUEST_TIMEOUT_SECONDS = 60

EXPECTED_MEDICATION_TEXT = "lisinopril 10 MG Oral Tablet"
EXPECTED_DOSE_VALUE = 10
EXPECTED_DOSE_UNIT = "mg"
EXPECTED_TIMING_CODE = "QD"
EXPECTED_ROUTE_CODE = "C38288"
EXPECTED_QUANTITY = 30
EXPECTED_REFILLS = 0


# Local OpenEMR uses a self-signed certificate.
# Suppress the warning only for this controlled lab.
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


def get_known_patient() -> dict:
    """
    Resolve the synthetic HL7 patient through the live
    OpenEMR FHIR Patient endpoint.
    """

    hl7_patient = load_hl7_patient()

    return get_fhir_patient(
        hl7_patient["identifier"]
    )


def authenticated_medication_request_search(
    patient_id: str,
) -> tuple[dict, float]:
    """
    Search live OpenEMR for MedicationRequest resources
    belonging to the known patient.
    """

    access_token = require_fresh_access_token()

    start_time = perf_counter()

    response = requests.get(
        f"{FHIR_BASE_URL}/MedicationRequest",
        params={
            "patient": patient_id,
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/fhir+json",
        },
        verify=False,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    duration_ms = (
        perf_counter() - start_time
    ) * 1000.0

    assert response.status_code == 200, (
        "FHIR MedicationRequest search failed: "
        f"HTTP {response.status_code}: "
        f"{response.text}"
    )

    payload = response.json()

    assert payload.get("resourceType") == "Bundle", (
        "FHIR MedicationRequest search expected "
        "a Bundle but received "
        f"{payload.get('resourceType')}."
    )

    return payload, duration_ms


def medication_requests(bundle: dict) -> list[dict]:
    """
    Return MedicationRequest resources from a search Bundle
    while rejecting unexpected resource types.
    """

    resources = []

    for entry in bundle.get("entry", []):
        resource = entry.get(
            "resource",
            {},
        )

        assert (
            resource.get("resourceType")
            == "MedicationRequest"
        ), (
            "MedicationRequest search Bundle contained "
            f"{resource.get('resourceType')}."
        )

        resources.append(resource)

    return resources


def find_expected_medication_request(
    bundle: dict,
) -> dict:
    """
    Locate exactly one logical instance of the controlled
    lisinopril prescription used by this interoperability lab.
    """

    matches = [
        resource
        for resource in medication_requests(bundle)
        if resource.get(
            "medicationCodeableConcept",
            {},
        ).get("text") == EXPECTED_MEDICATION_TEXT
    ]

    assert len(matches) == 1, (
        "Expected exactly one controlled "
        f"{EXPECTED_MEDICATION_TEXT!r} MedicationRequest "
        f"but found {len(matches)}."
    )

    return matches[0]


def test_authenticated_medication_request_search_by_patient():
    patient = get_known_patient()
    patient_id = patient["id"]

    bundle, duration_ms = (
        authenticated_medication_request_search(
            patient_id
        )
    )

    resources = medication_requests(bundle)

    assert len(resources) >= 1
    assert duration_ms > 0

    find_expected_medication_request(bundle)


def test_medication_request_preserves_clinical_semantics():
    patient = get_known_patient()
    patient_id = patient["id"]

    bundle, _ = (
        authenticated_medication_request_search(
            patient_id
        )
    )

    medication_request = (
        find_expected_medication_request(bundle)
    )

    assert medication_request["id"]

    assert (
        medication_request["subject"]["reference"]
        == f"Patient/{patient_id}"
    )

    assert medication_request["status"] == "active"
    assert medication_request["intent"] == "order"

    assert (
        medication_request[
            "medicationCodeableConcept"
        ]["text"]
        == EXPECTED_MEDICATION_TEXT
    )

    dosage = medication_request[
        "dosageInstruction"
    ][0]

    dose_quantity = dosage[
        "doseAndRate"
    ][0]["doseQuantity"]

    assert (
        dose_quantity["value"]
        == EXPECTED_DOSE_VALUE
    )

    assert (
        dose_quantity["unit"]
        == EXPECTED_DOSE_UNIT
    )

    timing = dosage["timing"]["code"]

    assert (
        timing["coding"][0]["code"]
        == EXPECTED_TIMING_CODE
    )

    route = dosage["route"]

    assert (
        route["coding"][0]["code"]
        == EXPECTED_ROUTE_CODE
    )

    dispense_request = medication_request[
        "dispenseRequest"
    ]

    assert (
        dispense_request["quantity"]["value"]
        == EXPECTED_QUANTITY
    )

    assert (
        dispense_request[
            "numberOfRepeatsAllowed"
        ]
        == EXPECTED_REFILLS
    )

    assert medication_request["authoredOn"]


def test_repeated_medication_reads_preserve_logical_identity():
    patient = get_known_patient()
    patient_id = patient["id"]

    first_bundle, _ = (
        authenticated_medication_request_search(
            patient_id
        )
    )

    second_bundle, _ = (
        authenticated_medication_request_search(
            patient_id
        )
    )

    first = find_expected_medication_request(
        first_bundle
    )

    second = find_expected_medication_request(
        second_bundle
    )

    assert first["id"] == second["id"]

    assert (
        first["subject"]["reference"]
        == second["subject"]["reference"]
    )

    assert first["status"] == second["status"]
    assert first["intent"] == second["intent"]

    assert (
        first["medicationCodeableConcept"]["text"]
        == second["medicationCodeableConcept"]["text"]
    )

    assert (
        first["authoredOn"]
        == second["authoredOn"]
    )

@pytest.mark.xfail(
    reason=(
        "OpenEMR currently reuses the medication dose unit "
        "for dispenseRequest.quantity, producing 30 mg even "
        "though dose quantity and dispense quantity represent "
        "different clinical concepts."
    ),
    strict=True,
)
def test_dispense_quantity_semantics_are_distinct_from_dose_quantity():
    patient = get_known_patient()
    patient_id = patient["id"]

    bundle, _ = authenticated_medication_request_search(
        patient_id
    )

    medication_request = find_expected_medication_request(
        bundle
    )

    dosage = medication_request[
        "dosageInstruction"
    ][0]

    dose_quantity = dosage[
        "doseAndRate"
    ][0]["doseQuantity"]

    dispense_quantity = medication_request[
        "dispenseRequest"
    ]["quantity"]

    # The medication dose is 10 mg.
    assert (
        dose_quantity["value"]
        == EXPECTED_DOSE_VALUE
    )

    assert (
        dose_quantity["unit"]
        == EXPECTED_DOSE_UNIT
    )

    # The prescription source quantity is 30.
    assert (
        dispense_quantity["value"]
        == EXPECTED_QUANTITY
    )

    # Dose quantity and dispense quantity are semantically
    # different measurements. OpenEMR currently reuses the
    # dose unit ("mg") for both.
    assert (
        dispense_quantity.get("unit")
        != dose_quantity.get("unit")
    ), (
        "MedicationRequest semantic defect: "
        f"doseQuantity is {dose_quantity.get('value')} "
        f"{dose_quantity.get('unit')}, while "
        f"dispenseRequest.quantity is "
        f"{dispense_quantity.get('value')} "
        f"{dispense_quantity.get('unit')}. "
        "The medication dose unit was reused for the "
        "dispense quantity."
    )
