from scripts.fhir.patient_helpers import (
    extract_fhir_identifier,
    get_fhir_patient,
    load_hl7_patient,
)


def result(expected, actual):
    return "PASS" if expected == actual else "FAIL"


def main():
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

    if not official_names:
        raise RuntimeError(
            "FHIR Patient has no official name."
        )

    fhir_name = official_names[0]

    comparisons = [
        (
            "Identifier",
            hl7_patient["identifier"],
            fhir_identifier,
        ),
        (
            "Family Name",
            hl7_patient["family"],
            fhir_name.get("family"),
        ),
        (
            "Given Name",
            hl7_patient["given"],
            fhir_name.get("given", [None])[0],
        ),
        (
            "Birth Date",
            hl7_patient["birthDate"],
            fhir_patient.get("birthDate"),
        ),
        (
            "Gender",
            hl7_patient["gender"],
            fhir_patient.get("gender"),
        ),
    ]

    print("=" * 78)
    print("HL7 v2 ADT -> FHIR PATIENT IDENTITY RECONCILIATION")
    print("=" * 78)
    print()
    print(
        f"{'Field':<16}"
        f"{'HL7 Source':<22}"
        f"{'FHIR Target':<22}"
        f"{'Result':<10}"
    )
    print("-" * 78)

    overall_pass = True

    for field, source, target in comparisons:
        comparison_result = result(source, target)

        if comparison_result == "FAIL":
            overall_pass = False

        print(
            f"{field:<16}"
            f"{str(source):<22}"
            f"{str(target):<22}"
            f"{comparison_result:<10}"
        )

    print("-" * 78)
    print()

    overall_result = (
        "PASS" if overall_pass else "FAIL"
    )

    print(f"Overall Result: {overall_result}")
    print()
    print("=" * 78)


if __name__ == "__main__":
    main()