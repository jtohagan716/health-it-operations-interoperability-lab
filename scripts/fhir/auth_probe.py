from pathlib import Path
from datetime import datetime, timezone
import json
import tempfile
import urllib3
import requests

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


FHIR_BASE_URL = "https://localhost:9300/apis/default/fhir"

TOKEN_FILE = Path(tempfile.gettempdir()) / "openemr-fhir-token.json"


def load_token_data(
    *,
    token_file: Path | None = None,
) -> dict:
    selected_token_file = token_file or TOKEN_FILE

    if not selected_token_file.exists():
        raise RuntimeError(
            "OpenEMR FHIR token file not found: "
            f"{selected_token_file}. "
            "Run scripts/get-openemr-fhir-token.ps1 first."
        )

    token_data = json.loads(
        selected_token_file.read_text(
            encoding="utf-8-sig"
        )
    )

    if not token_data.get("access_token"):
        raise RuntimeError(
            "FHIR token file does not contain an access_token."
        )

    return token_data


def parse_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def get_token_lifecycle(
    *,
    warning_threshold_seconds: int = 300,
    token_file: Path | None = None,
) -> dict:
    token_data = (
        load_token_data()
        if token_file is None
        else load_token_data(token_file=token_file)
    )

    acquired_at_raw = token_data.get(
        "acquired_at_utc"
    )
    expires_at_raw = token_data.get(
        "expires_at_utc"
    )

    if not acquired_at_raw or not expires_at_raw:
        raise RuntimeError(
            "Token lifecycle metadata is missing. "
            "Reacquire the token using "
            "scripts/get-openemr-fhir-token.ps1."
        )

    acquired_at = parse_utc_datetime(
        acquired_at_raw
    )
    expires_at = parse_utc_datetime(
        expires_at_raw
    )

    now = datetime.now(timezone.utc)

    remaining_seconds = int(
        (expires_at - now).total_seconds()
    )

    if remaining_seconds <= 0:
        state = "EXPIRED"
    elif remaining_seconds <= warning_threshold_seconds:
        state = "EXPIRING_SOON"
    else:
        state = "FRESH"

    return {
        "token_type": token_data.get("token_type"),
        "scope": token_data.get("scope", ""),
        "expires_in": token_data.get("expires_in"),
        "acquired_at": acquired_at,
        "expires_at": expires_at,
        "remaining_seconds": remaining_seconds,
        "state": state,
    }


def require_fresh_access_token(
    *,
    minimum_remaining_seconds: int = 300,
    token_file: Path | None = None,
) -> str:
    lifecycle = get_token_lifecycle(
        warning_threshold_seconds=(
            minimum_remaining_seconds
        ),
        token_file=token_file,
    )

    if lifecycle["state"] == "EXPIRED":
        raise RuntimeError(
            "FHIR authentication prerequisite failed: "
            "the access token has expired. "
            "Reacquire the SMART/FHIR token before running "
            "authenticated tests."
        )

    if lifecycle["state"] == "EXPIRING_SOON":
        raise RuntimeError(
            "FHIR authentication prerequisite failed: "
            f"the access token has only "
            f"{lifecycle['remaining_seconds']} "
            "seconds remaining. "
            "Reacquire the token before running "
            "the test suite."
        )

    token_data = (
        load_token_data()
        if token_file is None
        else load_token_data(token_file=token_file)
    )

    return token_data["access_token"]


def load_access_token() -> str:
    return load_token_data()["access_token"]


def fhir_get(
    resource_path: str,
    *,
    token: str | None = None,
    params: dict | None = None,
) -> requests.Response:
    headers = {
        "Accept": "application/fhir+json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return requests.get(
        f"{FHIR_BASE_URL}/{resource_path}",
        params=params,
        headers=headers,
        verify=False,
        timeout=30,
    )


def probe_patient_search(
    identifier: str,
    *,
    token: str | None = None,
) -> requests.Response:
    return fhir_get(
        "Patient",
        token=token,
        params={"identifier": identifier},
    )


def print_probe_result(
    scenario: str,
    response: requests.Response,
) -> None:
    print(f"\nScenario:    {scenario}")
    print(f"HTTP Status: {response.status_code}")
    print(
        "Content-Type:",
        response.headers.get(
            "Content-Type",
            "not returned",
        ),
    )

    if response.status_code >= 400:
        try:
            payload = response.json()

            print(
                "Error:",
                payload.get(
                    "error",
                    "not returned",
                ),
            )
            print(
                "Message:",
                payload.get(
                    "message",
                    "not returned",
                ),
            )

        except ValueError:
            print(
                "Response body: non-JSON error response"
            )


def print_token_lifecycle() -> None:
    lifecycle = get_token_lifecycle()

    print("\nSMART/FHIR AUTHENTICATION PREREQUISITE")
    print("------------------------------------")
    print(
        f"Token type:          "
        f"{lifecycle['token_type']}"
    )
    print(
        f"Configured lifetime: "
        f"{lifecycle['expires_in']} seconds"
    )
    print(
        f"Acquired UTC:        "
        f"{lifecycle['acquired_at'].isoformat()}"
    )
    print(
        f"Expires UTC:         "
        f"{lifecycle['expires_at'].isoformat()}"
    )
    print(
        f"Remaining lifetime:  "
        f"{lifecycle['remaining_seconds']} seconds"
    )
    print(
        f"State:               "
        f"{lifecycle['state']}"
    )