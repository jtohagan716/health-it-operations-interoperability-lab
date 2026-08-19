from datetime import datetime


FHIR_IDENTIFIER_TYPE_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/v2-0203"
)

IDENTIFIER_TYPE_DISPLAY = {
    "MR": "Medical record number",
}

NAME_TYPE_TO_FHIR_USE = {
    "L": "official",
}

ADMINISTRATIVE_SEX_TO_FHIR_GENDER = {
    "M": "male",
    "F": "female",
    "O": "other",
    "U": "unknown",
}

ASSIGNING_AUTHORITY_TO_IDENTIFIER_SYSTEM = {
    "INTEROPLAB": "https://example.org/fhir/sid/interoplab-mrn",
}


def format_hl7_date_as_fhir_date(value: str) -> str:
    parsed_date = datetime.strptime(value, "%Y%m%d")

    return parsed_date.strftime("%Y-%m-%d")


def map_adt_to_fhir_patient(adt: dict) -> dict:
    identifier_type = adt["identifier_type"]
    name_type = adt["name_type"]
    administrative_sex = adt["administrative_sex"]
    assigning_authority = adt["assigning_authority"]

    return {
        "resourceType": "Patient",
        "identifier": [
            {
                "system": ASSIGNING_AUTHORITY_TO_IDENTIFIER_SYSTEM[
                    assigning_authority
                ],
                "value": adt["patient_id"],
                "assigner": {
                    "display": assigning_authority,
                },
                "type": {
                    "coding": [
                        {
                            "system": FHIR_IDENTIFIER_TYPE_SYSTEM,
                            "code": identifier_type,
                            "display": IDENTIFIER_TYPE_DISPLAY[
                                identifier_type
                            ],
                        }
                    ]
                },
            }
        ],
        "name": [
            {
                "use": NAME_TYPE_TO_FHIR_USE[name_type],
                "family": adt["family_name"],
                "given": [
                    adt["given_name"],
                ],
            }
        ],
        "birthDate": format_hl7_date_as_fhir_date(
            adt["date_of_birth"]
        ),
        "gender": ADMINISTRATIVE_SEX_TO_FHIR_GENDER[
            administrative_sex
        ],
    }
