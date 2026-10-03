from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests

from scripts.fhir.map_adt_to_patient import map_adt_to_fhir_patient
from scripts.fhir.map_oru_to_diagnostic_report import (
    map_oru_to_fhir_diagnostic_report,
)
from scripts.fhir.map_oru_to_observation import (
    map_oru_to_fhir_observation,
)
from scripts.hl7.analyze_adt import analyze_adt
from scripts.hl7.analyze_oru import analyze_oru


DEFAULT_BASE_URL = os.getenv(
    "HAPI_FHIR_BASE_URL",
    "http://localhost:8090/fhir",
).rstrip("/")

DEFAULT_ADT_FIXTURE = Path(
    "fixtures/hl7/adt/adt-a04-lab000001.hl7"
)

DEFAULT_ORU_FIXTURE = Path(
    "fixtures/hl7/oru/oru-r01-lab000001.hl7"
)

FHIR_HEADERS = {
    "Accept": "application/fhir+json",
}

FHIR_JSON_HEADERS = {
    "Accept": "application/fhir+json",
    "Content-Type": "application/fhir+json",
}


def identifier_token(identifier: dict) -> str:
    return (
        f"{identifier['system']}|"
        f"{identifier['value']}"
    )


def read_resource(
    session: requests.Session,
    base_url: str,
    resource_type: str,
    resource_id: str,
) -> dict:
    response = session.get(
        f"{base_url}/{resource_type}/{resource_id}",
        headers=FHIR_HEADERS,
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"FHIR read failed for "
            f"{resource_type}/{resource_id}: "
            f"HTTP {response.status_code}: {response.text}"
        )

    return response.json()


def find_by_identifier(
    session: requests.Session,
    base_url: str,
    resource_type: str,
    identifier: dict,
) -> dict | None:
    response = session.get(
        f"{base_url}/{resource_type}",
        params={
            "identifier": identifier_token(identifier),
        },
        headers=FHIR_HEADERS,
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"FHIR identifier search failed for "
            f"{resource_type}: "
            f"HTTP {response.status_code}: {response.text}"
        )

    bundle = response.json()
    entries = bundle.get("entry", [])

    if not entries:
        return None

    return entries[0]["resource"]


def create_resource(
    session: requests.Session,
    base_url: str,
    resource: dict,
) -> dict:
    resource_type = resource["resourceType"]

    response = session.post(
        f"{base_url}/{resource_type}",
        headers=FHIR_JSON_HEADERS,
        json=resource,
        timeout=60,
    )

    if response.status_code != 201:
        raise RuntimeError(
            f"FHIR create failed for "
            f"{resource_type}: "
            f"HTTP {response.status_code}: {response.text}"
        )

    return response.json()


def find_or_create(
    session: requests.Session,
    base_url: str,
    resource: dict,
) -> tuple[dict, str]:
    identifier = resource["identifier"][0]

    existing = find_by_identifier(
        session,
        base_url,
        resource["resourceType"],
        identifier,
    )

    if existing is not None:
        return existing, "reused"

    return (
        create_resource(session, base_url, resource),
        "created",
    )


def search_observations(
    session: requests.Session,
    base_url: str,
    patient_id: str,
    observation_code: str,
) -> dict:
    response = session.get(
        f"{base_url}/Observation",
        params={
            "patient": patient_id,
            "code": observation_code,
        },
        headers=FHIR_HEADERS,
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"FHIR Observation search failed: "
            f"HTTP {response.status_code}: {response.text}"
        )

    return response.json()


def publish_capstone(
    *,
    adt_fixture: Path = DEFAULT_ADT_FIXTURE,
    oru_fixture: Path = DEFAULT_ORU_FIXTURE,
    base_url: str = DEFAULT_BASE_URL,
) -> dict:
    adt = analyze_adt(adt_fixture)
    oru = analyze_oru(oru_fixture)

    patient_resource = map_adt_to_fhir_patient(adt)

    patient, patient_action = find_or_create(
        requests.Session(),
        base_url,
        patient_resource,
    )

    patient_id = patient["id"]
    patient_reference = f"Patient/{patient_id}"

    patient_identifier = patient_resource["identifier"][0]

    observation_resource = map_oru_to_fhir_observation(oru)
    observation_resource["subject"] = {
        "reference": patient_reference,
        "identifier": patient_identifier,
    }

    session = requests.Session()

    observation, observation_action = find_or_create(
        session,
        base_url,
        observation_resource,
    )

    observation_id = observation["id"]
    observation_reference = (
        f"Observation/{observation_id}"
    )

    report_resource = map_oru_to_fhir_diagnostic_report(
        oru,
        observation_reference=observation_reference,
    )

    report_resource["subject"] = {
        "reference": patient_reference,
        "identifier": patient_identifier,
    }

    report, report_action = find_or_create(
        session,
        base_url,
        report_resource,
    )

    persisted_patient = read_resource(
        session,
        base_url,
        "Patient",
        patient_id,
    )

    persisted_observation = read_resource(
        session,
        base_url,
        "Observation",
        observation_id,
    )

    persisted_report = read_resource(
        session,
        base_url,
        "DiagnosticReport",
        report["id"],
    )

    observation_search = search_observations(
        session,
        base_url,
        patient_id,
        oru["observation_code"],
    )

    checks = {
        "patient_identity_preserved": (
            persisted_patient["identifier"][0]["value"]
            == adt["patient_id"]
            == oru["patient_id"]
        ),
        "observation_subject_links_patient": (
            persisted_observation["subject"]["reference"]
            == patient_reference
        ),
        "observation_code_preserved": (
            persisted_observation["code"]["coding"][0]["code"]
            == oru["observation_code"]
        ),
        "observation_value_preserved": (
            float(
                persisted_observation[
                    "valueQuantity"
                ]["value"]
            )
            == float(oru["observation_value"])
        ),
        "observation_units_preserved": (
            persisted_observation[
                "valueQuantity"
            ]["unit"]
            == oru["observation_units"]
        ),
        "diagnostic_report_subject_links_patient": (
            persisted_report["subject"]["reference"]
            == patient_reference
        ),
        "diagnostic_report_links_observation": (
            persisted_report["result"][0]["reference"]
            == observation_reference
        ),
        "observation_search_finds_result": (
            any(
                entry["resource"]["id"]
                == observation_id
                for entry in observation_search.get(
                    "entry",
                    [],
                )
            )
        ),
    }

    return {
        "source": {
            "adt_control_id": adt["message_control_id"],
            "oru_control_id": oru["message_control_id"],
            "patient_id": adt["patient_id"],
            "placer_order": oru["placer_order_number"],
            "filler_order": oru["filler_order_number"],
        },
        "actions": {
            "patient": patient_action,
            "observation": observation_action,
            "diagnostic_report": report_action,
        },
        "resources": {
            "patient": patient_reference,
            "observation": observation_reference,
            "diagnostic_report": (
                f"DiagnosticReport/{report['id']}"
            ),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Publish the synthetic ADT/ORU workflow "
            "to HAPI FHIR."
        )
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
    )

    parser.add_argument(
        "--adt",
        type=Path,
        default=DEFAULT_ADT_FIXTURE,
    )

    parser.add_argument(
        "--oru",
        type=Path,
        default=DEFAULT_ORU_FIXTURE,
    )

    args = parser.parse_args()

    result = publish_capstone(
        adt_fixture=args.adt,
        oru_fixture=args.oru,
        base_url=args.base_url,
    )

    print(json.dumps(result, indent=2))

    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()