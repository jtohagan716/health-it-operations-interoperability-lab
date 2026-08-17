from scripts.fhir.auth_probe import (
    require_fresh_access_token,
    print_probe_result,
    print_token_lifecycle,
    probe_patient_search,
)


PATIENT_IDENTIFIER = "LAB000001"


def main() -> None:
    print_token_lifecycle()

    missing_token_response = probe_patient_search(
        PATIENT_IDENTIFIER,
        token=None,
    )

    print_probe_result(
        "Missing bearer token",
        missing_token_response,
    )

    invalid_token_response = probe_patient_search(
        PATIENT_IDENTIFIER,
        token="invalid-test-token",
    )

    print_probe_result(
        "Invalid bearer token",
        invalid_token_response,
    )

    valid_token = require_fresh_access_token()

    valid_token_response = probe_patient_search(
        PATIENT_IDENTIFIER,
        token=valid_token,
    )

    print_probe_result(
        "Valid bearer token",
        valid_token_response,
    )


if __name__ == "__main__":
    main()