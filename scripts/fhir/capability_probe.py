import requests
import urllib3

FHIR_BASE_URL = "https://127.0.0.1:9300/apis/default/fhir"

# Local OpenEMR uses a self-signed certificate.
# Suppress the warning for this controlled development lab only.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_capability_statement() -> dict:
    response = requests.get(
        f"{FHIR_BASE_URL}/metadata",
        verify=False,
        timeout=15,
    )

    response.raise_for_status()

    return response.json()


def find_resource(capability_statement: dict, resource_type: str) -> dict | None:
    for rest_block in capability_statement.get("rest", []):
        for resource in rest_block.get("resource", []):
            if resource.get("type") == resource_type:
                return resource

    return None


def main() -> None:
    capability = get_capability_statement()

    print("=" * 60)
    print("FHIR CAPABILITY PROBE")
    print("=" * 60)

    print(f"Resource Type : {capability.get('resourceType')}")
    print(f"FHIR Version  : {capability.get('fhirVersion')}")

    rest_modes = [
        rest.get("mode")
        for rest in capability.get("rest", [])
    ]

    print(f"REST Modes    : {', '.join(rest_modes)}")

    patient = find_resource(capability, "Patient")

    if patient is None:
        print("\nPatient       : NOT ADVERTISED")
        return

    print("\nPatient       : ADVERTISED")

    print("\nInteractions")
    print("-" * 60)

    interactions = [
        interaction.get("code")
        for interaction in patient.get("interaction", [])
    ]

    for interaction in interactions:
        print(interaction)

    print("\nSearch Parameters")
    print("-" * 60)

    search_parameters = [
        parameter.get("name")
        for parameter in patient.get("searchParam", [])
    ]

    for parameter in search_parameters:
        print(parameter)

    print("\nSupported Profiles")
    print("-" * 60)

    for profile in patient.get("supportedProfile", []):
        print(profile)


if __name__ == "__main__":
    main()