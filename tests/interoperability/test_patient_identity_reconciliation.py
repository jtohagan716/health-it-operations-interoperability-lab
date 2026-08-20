from scripts.fhir.patient_helpers import (
    extract_fhir_identifier,
    get_fhir_patient,
    load_hl7_patient,
)


def test_openemr_fhir_matches_hl7_patient_identity():
    hl7_patient = load_hl7_patient()

    fhir_patient = get_fhir_patient(
        hl7_patient["identifier"]
    )

    fhir_identifier = extract_fhir_identifier(
        fhir_patient
    )

    official_names = [
        name
        for name in fhir_patient.get("name", [])
        if name.get("use") == "official"
    ]

    assert official_names, (
        "FHIR Patient has no official name."
    )

    fhir_name = official_names[0]

    assert (
        fhir_identifier
        == hl7_patient["identifier"]
    )

    assert (
        fhir_name["family"]
        == hl7_patient["family"]
    )

    assert (
        fhir_name["given"][0]
        == hl7_patient["given"]
    )

    assert (
        fhir_patient["birthDate"]
        == hl7_patient["birthDate"]
    )

    assert (
        fhir_patient["gender"]
        == hl7_patient["gender"]
    )