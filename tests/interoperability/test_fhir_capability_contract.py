from scripts.fhir.capability_probe import (
    find_resource,
    get_capability_statement,
)


def test_server_returns_capability_statement():
    capability = get_capability_statement()

    assert capability.get("resourceType") == "CapabilityStatement"


def test_server_advertises_fhir_r4():
    capability = get_capability_statement()

    assert capability.get("fhirVersion") == "4.0.1"


def test_patient_resource_is_advertised():
    capability = get_capability_statement()

    patient = find_resource(capability, "Patient")

    assert patient is not None


def test_patient_read_interaction_is_advertised():
    capability = get_capability_statement()
    patient = find_resource(capability, "Patient")

    interactions = {
        interaction.get("code")
        for interaction in patient.get("interaction", [])
    }

    assert "read" in interactions


def test_patient_identifier_search_is_advertised():
    capability = get_capability_statement()
    patient = find_resource(capability, "Patient")

    search_parameters = {
        parameter.get("name")
        for parameter in patient.get("searchParam", [])
    }

    assert "identifier" in search_parameters