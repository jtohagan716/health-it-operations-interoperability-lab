import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
import urllib3

from scripts.fhir.auth_probe import (
    load_token_data,
    require_fresh_access_token,
)


warnings.filterwarnings(
    "ignore",
    category=urllib3.exceptions.InsecureRequestWarning,
)


FHIR_BASE_URL = os.getenv(
    "OPENEMR_FHIR_BASE_URL",
    "https://localhost:9340/apis/default/fhir",
).rstrip("/")

PATIENT_ID = os.getenv(
    "OPENEMR_FHIR_PATIENT_ID",
    "",
)

LOINC_CODE = "2345-7"

LOINC_DISPLAY = (
    "Glucose [Mass/volume] in Serum or Plasma"
)


def require_token_file(
    environment_variable: str,
) -> Path:
    raw_path = os.getenv(environment_variable)

    if not raw_path:
        pytest.skip(
            f"{environment_variable} is required"
        )

    token_file = Path(raw_path)

    if not token_file.exists():
        pytest.skip(
            f"Token file not found: {token_file}"
        )

    return token_file


def load_token_with_scope(
    token_file: Path,
    required_scope: str,
) -> str:
    token_data = load_token_data(
        token_file=token_file
    )

    scopes = set(
        token_data.get("scope", "").split()
    )

    assert required_scope in scopes, (
        f"{required_scope} missing from "
        f"{token_file}. "
        f"Granted scopes: {sorted(scopes)}"
    )

    return require_fresh_access_token(
        token_file=token_file
    )


def delete_service_request(
    access_token: str,
    service_request_id: str,
) -> requests.Response:
    return requests.delete(
        f"{FHIR_BASE_URL}/ServiceRequest/"
        f"{service_request_id}",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Accept": "application/fhir+json",
        },
        verify=False,
        timeout=30,
    )


def test_servicerequest_write_read_and_scope_boundary():
    if not PATIENT_ID:
        pytest.skip(
            "OPENEMR_FHIR_PATIENT_ID is required"
        )

    write_token_file = require_token_file(
        "OPENEMR_FHIR_WRITE_TOKEN_FILE"
    )

    read_token_file = require_token_file(
        "OPENEMR_FHIR_READ_TOKEN_FILE"
    )

    write_token = load_token_with_scope(
        write_token_file,
        "user/ServiceRequest.cud",
    )

    read_token = load_token_with_scope(
        read_token_file,
        "user/ServiceRequest.rs",
    )

    read_token_data = load_token_data(
        token_file=read_token_file
    )

    read_scopes = set(
        read_token_data.get("scope", "").split()
    )

    assert (
        "user/ServiceRequest.cud"
        not in read_scopes
    ), (
        "Read token unexpectedly contains the "
        "ServiceRequest CUD scope."
    )

    request_payload = {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "priority": "routine",
        "subject": {
            "reference": (
                f"Patient/{PATIENT_ID}"
            )
        },
        "code": {
            "coding": [
                {
                    "system": (
                        "http://loinc.org"
                    ),
                    "code": LOINC_CODE,
                    "display": LOINC_DISPLAY,
                }
            ],
            "text": LOINC_DISPLAY,
        },
        "authoredOn": (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        ),
    }

    created_resource_ids = []

    write_response = requests.post(
        f"{FHIR_BASE_URL}/ServiceRequest",
        headers={
            "Authorization": (
                f"Bearer {write_token}"
            ),
            "Accept": "application/fhir+json",
            "Content-Type": (
                "application/fhir+json"
            ),
        },
        json=request_payload,
        verify=False,
        timeout=30,
    )

    assert write_response.status_code == 201, (
        "ServiceRequest create failed: "
        f"{write_response.status_code} "
        f"{write_response.text}"
    )

    created = write_response.json()

    service_request_id = created.get("uuid")

    assert service_request_id, (
        "OpenEMR create response did not contain "
        f"uuid: {created}"
    )

    created_resource_ids.append(
        service_request_id
    )

    try:
        read_response = requests.get(
            f"{FHIR_BASE_URL}/ServiceRequest/"
            f"{service_request_id}",
            headers={
                "Authorization": (
                    f"Bearer {read_token}"
                ),
                "Accept": "application/fhir+json",
            },
            verify=False,
            timeout=30,
        )

        assert read_response.status_code == 200, (
            "ServiceRequest read-back failed: "
            f"{read_response.status_code} "
            f"{read_response.text}"
        )

        read_back = read_response.json()

        assert (
            read_back["resourceType"]
            == "ServiceRequest"
        )

        assert (
            read_back["id"]
            == service_request_id
        )

        assert read_back["status"] == "active"
        assert read_back["intent"] == "order"

        assert (
            read_back["subject"]["reference"]
            == f"Patient/{PATIENT_ID}"
        )

        assert (
            read_back["code"]["text"]
            == LOINC_DISPLAY
        )

        negative_response = requests.post(
            f"{FHIR_BASE_URL}/ServiceRequest",
            headers={
                "Authorization": (
                    f"Bearer {read_token}"
                ),
                "Accept": "application/fhir+json",
                "Content-Type": (
                    "application/fhir+json"
                ),
            },
            json=request_payload,
            verify=False,
            timeout=30,
        )

        if negative_response.status_code == 201:
            negative_created = (
                negative_response.json()
            )

            negative_id = (
                negative_created.get("uuid")
            )

            if negative_id:
                created_resource_ids.append(
                    negative_id
                )

        assert negative_response.status_code in {
            401,
            403,
        }, (
            "Read-only token unexpectedly "
            "created a ServiceRequest: "
            f"{negative_response.status_code} "
            f"{negative_response.text}"
        )

    finally:
        cleanup_failures = []

        for resource_id in reversed(
            created_resource_ids
        ):
            cleanup_response = (
                delete_service_request(
                    write_token,
                    resource_id,
                )
            )
# OpenEMR does not advertise ServiceRequest delete.
# HTTP 404 is therefore expected; the isolated test
# resource remains in the disposable validation site.

            if cleanup_response.status_code not in {
                200,
                204,
                404,
            }:
                cleanup_failures.append(
                    (
                        resource_id,
                        cleanup_response.status_code,
                        cleanup_response.text,
                    )
                )

        assert not cleanup_failures, (
            "ServiceRequest cleanup failed: "
            f"{cleanup_failures}"
        )