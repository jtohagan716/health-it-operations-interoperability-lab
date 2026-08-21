import requests
import urllib3


FHIR_BASE_URL = (
    "https://127.0.0.1:9300/apis/default/fhir"
)

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


def get_capability_statement() -> dict:
    response = requests.get(
        f"{FHIR_BASE_URL}/metadata",
        verify=False,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def find_resource(
    capability: dict,
    resource_type: str,
) -> dict:
    for rest in capability.get("rest", []):
        for resource in rest.get("resource", []):
            if resource.get("type") == resource_type:
                return resource

    raise AssertionError(
        f"{resource_type} is not advertised"
    )


def interaction_codes(
    resource: dict,
) -> set[str]:
    return {
        interaction["code"]
        for interaction in resource.get(
            "interaction",
            []
        )
    }


def search_parameters(
    resource: dict,
) -> set[str]:
    return {
        parameter["name"]
        for parameter in resource.get(
            "searchParam",
            []
        )
    }


def test_observation_supports_required_lab_result_contract():
    capability = get_capability_statement()

    observation = find_resource(
        capability,
        "Observation",
    )

    interactions = interaction_codes(
        observation
    )

    searches = search_parameters(
        observation
    )

    assert "read" in interactions
    assert "search-type" in interactions

    assert "patient" in searches
    assert "code" in searches
    assert "date" in searches


def test_diagnostic_report_supports_required_lab_contract():
    capability = get_capability_statement()

    report = find_resource(
        capability,
        "DiagnosticReport",
    )

    interactions = interaction_codes(
        report
    )

    searches = search_parameters(
        report
    )

    assert "read" in interactions
    assert "search-type" in interactions

    assert "patient" in searches
    assert "code" in searches
    assert "date" in searches


def test_lab_resources_do_not_advertise_write_contract():
    capability = get_capability_statement()

    for resource_type in (
        "Observation",
        "DiagnosticReport",
    ):
        resource = find_resource(
            capability,
            resource_type,
        )

        interactions = interaction_codes(
            resource
        )

        assert "create" not in interactions
        assert "update" not in interactions