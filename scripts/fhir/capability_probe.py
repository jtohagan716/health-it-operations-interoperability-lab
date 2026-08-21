import requests
import urllib3

FHIR_BASE_URL = "https://127.0.0.1:9300/apis/default/fhir"

# Local OpenEMR uses a self-signed certificate.
# Suppress the warning for this controlled development lab only.
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
    capability_statement: dict,
    resource_type: str,
) -> dict | None:
    for rest_block in capability_statement.get(
        "rest",
        [],
    ):
        for resource in rest_block.get(
            "resource",
            [],
        ):
            if resource.get("type") == resource_type:
                return resource

    return None


def print_resource_summary(
    capability_statement: dict,
    resource_type: str,
) -> None:
    resource = find_resource(
        capability_statement,
        resource_type,
    )

    print()
    print(resource_type)
    print("-" * 60)

    if resource is None:
        print("Status          : NOT ADVERTISED")
        return

    print("Status          : ADVERTISED")

    interactions = [
        interaction.get("code")
        for interaction in resource.get(
            "interaction",
            [],
        )
    ]

    print()
    print("Interactions")
    print("-" * 60)

    if interactions:
        for interaction in interactions:
            print(interaction)
    else:
        print("(none advertised)")

    print()
    print("Search Parameters")
    print("-" * 60)

    search_parameters = [
        parameter.get("name")
        for parameter in resource.get(
            "searchParam",
            [],
        )
    ]

    if search_parameters:
        for parameter in search_parameters:
            print(parameter)
    else:
        print("(none advertised)")

    print()
    print("Supported Profiles")
    print("-" * 60)

    supported_profiles = resource.get(
        "supportedProfile",
        [],
    )

    if supported_profiles:
        for profile in supported_profiles:
            print(profile)
    else:
        print("(none advertised)")


def main() -> None:
    capability = get_capability_statement()

    print("=" * 60)
    print("FHIR CAPABILITY PROBE")
    print("=" * 60)

    print(
        f"Resource Type : "
        f"{capability.get('resourceType')}"
    )

    print(
        f"FHIR Version  : "
        f"{capability.get('fhirVersion')}"
    )

    rest_modes = [
        rest.get("mode")
        for rest in capability.get(
            "rest",
            [],
        )
    ]

    print(
        f"REST Modes    : "
        f"{', '.join(rest_modes)}"
    )

    for resource_type in (
        "Patient",
        "Observation",
        "DiagnosticReport",
    ):
        print_resource_summary(
            capability,
            resource_type,
        )


if __name__ == "__main__":
    main()