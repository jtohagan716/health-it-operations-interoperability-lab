from pathlib import Path

from scripts.hl7.analyze_adt import analyze_adt
from scripts.fhir.map_adt_to_patient import map_adt_to_fhir_patient


HL7_FIXTURE = Path(
    "fixtures/hl7/adt/adt-a04-lab000001.hl7"
)


def test_maps_pid_3_patient_identifier_value_to_fhir_patient():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    assert patient["resourceType"] == "Patient"
    assert patient["identifier"][0]["value"] == adt["patient_id"]
    assert patient["identifier"][0]["value"] == "LAB000001"

def test_maps_pid_3_identifier_type_to_fhir_identifier_type():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    coding = patient["identifier"][0]["type"]["coding"][0]

    assert coding["system"] == (
        "http://terminology.hl7.org/CodeSystem/v2-0203"
    )
    assert coding["code"] == adt["identifier_type"]
    assert coding["code"] == "MR"
    assert coding["display"] == "Medical record number"

def test_maps_pid_5_legal_name_to_fhir_official_name():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    name = patient["name"][0]

    assert name["family"] == adt["family_name"]
    assert name["family"] == "Testpatient"

    assert name["given"][0] == adt["given_name"]
    assert name["given"][0] == "Avery"

    assert adt["name_type"] == "L"
    assert name["use"] == "official"

def test_maps_pid_7_birth_date_to_fhir_birth_date():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    assert adt["date_of_birth"] == "19800115"
    assert patient["birthDate"] == "1980-01-15"

def test_maps_pid_8_administrative_sex_to_fhir_gender():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    assert adt["administrative_sex"] == "M"
    assert patient["gender"] == "male"

def test_maps_pid_3_assigning_authority_to_fhir_identifier_namespace():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    identifier = patient["identifier"][0]

    assert adt["assigning_authority"] == "INTEROPLAB"

    assert identifier["system"] == (
        "https://example.org/fhir/sid/interoplab-mrn"
    )

    assert identifier["assigner"]["display"] == "INTEROPLAB"

def test_unknown_assigning_authority_is_rejected(tmp_path):
    source = HL7_FIXTURE.read_text(encoding="utf-8")

    known_identifier = "LAB000001^^^INTEROPLAB^MR"
    unknown_identifier = "LAB000001^^^UNKNOWNLAB^MR"

    assert known_identifier in source

    modified_message = source.replace(
        known_identifier,
        unknown_identifier,
        1,
    )

    modified_fixture = tmp_path / "adt-a04-unknown-authority.hl7"
    modified_fixture.write_text(
        modified_message,
        encoding="utf-8",
    )

    adt = analyze_adt(modified_fixture)

    assert adt["assigning_authority"] == "UNKNOWNLAB"

    try:
        map_adt_to_fhir_patient(adt)
    except KeyError as exc:
        assert exc.args[0] == "UNKNOWNLAB"
    else:
        raise AssertionError(
            "Unknown assigning authority must not receive "
            "an invented FHIR identifier namespace."
        )

def test_maps_valid_adt_a04_to_expected_fhir_patient():
    adt = analyze_adt(HL7_FIXTURE)

    patient = map_adt_to_fhir_patient(adt)

    expected_patient = {
        "resourceType": "Patient",
        "identifier": [
            {
                "system": (
                    "https://example.org/fhir/sid/interoplab-mrn"
                ),
                "value": "LAB000001",
                "assigner": {
                    "display": "INTEROPLAB",
                },
                "type": {
                    "coding": [
                        {
                            "system": (
                                "http://terminology.hl7.org/"
                                "CodeSystem/v2-0203"
                            ),
                            "code": "MR",
                            "display": "Medical record number",
                        }
                    ]
                },
            }
        ],
        "name": [
            {
                "use": "official",
                "family": "Testpatient",
                "given": [
                    "Avery",
                ],
            }
        ],
        "birthDate": "1980-01-15",
        "gender": "male",
    }

    assert patient == expected_patient
