import requests
import urllib3


SMART_CONFIG_URL = (
    "https://localhost:9300/apis/default/fhir/"
    ".well-known/smart-configuration"
)


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


def get_smart_configuration() -> dict:
    response = requests.get(
        SMART_CONFIG_URL,
        verify=False,
        timeout=30,
        headers={
            "Accept": "application/json",
        },
    )

    assert response.status_code == 200, (
        "SMART configuration discovery failed: "
        f"HTTP {response.status_code}: {response.text}"
    )

    payload = response.json()

    assert isinstance(payload, dict), (
        "SMART configuration response was not a JSON object."
    )

    return payload


def test_smart_configuration_is_discoverable():
    payload = get_smart_configuration()

    assert payload


def test_smart_configuration_advertises_authorization_endpoint():
    payload = get_smart_configuration()

    authorization_endpoint = payload.get(
        "authorization_endpoint"
    )

    assert authorization_endpoint, (
        "SMART configuration does not advertise "
        "authorization_endpoint."
    )

    assert authorization_endpoint.startswith("https://")


def test_smart_configuration_advertises_token_endpoint():
    payload = get_smart_configuration()

    token_endpoint = payload.get(
        "token_endpoint"
    )

    assert token_endpoint, (
        "SMART configuration does not advertise token_endpoint."
    )

    assert token_endpoint.startswith("https://")


def test_smart_configuration_advertises_supported_scopes():
    payload = get_smart_configuration()

    scopes_supported = payload.get(
        "scopes_supported",
        [],
    )

    assert scopes_supported, (
        "SMART configuration does not advertise scopes_supported."
    )

    # OpenEMR currently advertises scopes_supported as a nested
    # collection. Normalize the structure before evaluating the
    # advertised SMART authorization contract.
    normalized_scopes = set()

    for scope_group in scopes_supported:
        if isinstance(scope_group, list):
            normalized_scopes.update(scope_group)
        else:
            normalized_scopes.add(scope_group)

    expected_scopes = {
        "openid",
        "fhirUser",
        "user/Patient.rs",
        "user/Encounter.rs",
        "user/Observation.rs",
    }

    missing_scopes = expected_scopes - normalized_scopes

    assert not missing_scopes, (
        "SMART configuration is missing expected scopes: "
        f"{sorted(missing_scopes)}"
    )
    
def test_smart_configuration_advertises_capabilities():
    payload = get_smart_configuration()

    capabilities = payload.get(
        "capabilities",
        [],
    )

    assert capabilities, (
        "SMART configuration does not advertise capabilities."
    )


def test_authorization_and_token_endpoints_share_expected_host():
    payload = get_smart_configuration()

    authorization_endpoint = payload[
        "authorization_endpoint"
    ]

    token_endpoint = payload[
        "token_endpoint"
    ]

    assert "localhost:9300" in authorization_endpoint
    assert "localhost:9300" in token_endpoint