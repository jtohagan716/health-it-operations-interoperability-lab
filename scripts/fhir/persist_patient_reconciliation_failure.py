from scripts.fhir.patient_helpers import (
    extract_fhir_identifier,
    get_fhir_patient,
    load_hl7_patient,
)

from scripts.fhir.validation_store import (
    complete_validation_run,
    create_validation_run,
    find_transaction_id,
    record_fhir_lineage,
    record_validation_result,
)


MESSAGE_CONTROL_ID = "LAB-A04-000001"
FHIR_VERSION = "4.0.1"
FHIR_ENDPOINT = "https://localhost:9300/apis/default/fhir"


def status(expected, actual):
    return "PASS" if expected == actual else "FAIL"


def main():
    hl7_patient = load_hl7_patient()

    fhir_patient = get_fhir_patient(
        hl7_patient["identifier"]
    )

    transaction_id = find_transaction_id(
        MESSAGE_CONTROL_ID
    )

    fhir_resource_id = fhir_patient["id"]

    profiles = (
        fhir_patient
        .get("meta", {})
        .get("profile", [])
    )

    profile_url = (
        profiles[0]
        if profiles
        else None
    )

    fhir_lineage_id = record_fhir_lineage(
        transaction_id=transaction_id,
        resource_type="Patient",
        resource_id=fhir_resource_id,
        fhir_version=FHIR_VERSION,
        profile_url=profile_url,
        endpoint=FHIR_ENDPOINT,
    )

    validation_run_id = create_validation_run(
        fhir_lineage_id=fhir_lineage_id,
        run_type="RECONCILIATION",
        scenario_name="patient_identity_reconciliation_birthdate_failure",
        synthetic=True,
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
        complete_validation_run(
            validation_run_id=validation_run_id,
            overall_status="ERROR",
        )

        raise RuntimeError(
            "FHIR Patient has no official name."
        )

    fhir_name = official_names[0]

    # Controlled defect injection.
    #
    # OpenEMR is NOT modified.
    # We simulate an incorrect observed FHIR birth date
    # only inside this validation execution.
    synthetic_birth_date = "1980-01-16"

    comparisons = [
        {
            "rule": "HL7 PID-3 matches FHIR Patient.identifier",
            "source": "PID-3",
            "target": "Patient.identifier",
            "expected": hl7_patient["identifier"],
            "actual": fhir_identifier,
        },
        {
            "rule": "HL7 PID-5 family matches FHIR Patient.name.family",
            "source": "PID-5",
            "target": "Patient.name.family",
            "expected": hl7_patient["family"],
            "actual": fhir_name.get("family"),
        },
        {
            "rule": "HL7 PID-5 given matches FHIR Patient.name.given",
            "source": "PID-5",
            "target": "Patient.name.given",
            "expected": hl7_patient["given"],
            "actual": fhir_name.get(
                "given",
                [None],
            )[0],
        },
        {
            "rule": "HL7 PID-7 matches FHIR Patient.birthDate",
            "source": "PID-7",
            "target": "Patient.birthDate",
            "expected": hl7_patient["birthDate"],
            "actual": synthetic_birth_date,
        },
        {
            "rule": "HL7 PID-8 matches FHIR Patient.gender",
            "source": "PID-8",
            "target": "Patient.gender",
            "expected": hl7_patient["gender"],
            "actual": fhir_patient.get(
                "gender"
            ),
        },
    ]

    print("=" * 72)
    print("PERSISTING SYNTHETIC FHIR VALIDATION FAILURE")
    print("=" * 72)

    print(
        f"Transaction ID    : "
        f"{transaction_id}"
    )

    print(
        f"FHIR Lineage ID   : "
        f"{fhir_lineage_id}"
    )

    print(
        f"Validation Run ID : "
        f"{validation_run_id}"
    )

    print(
        f"FHIR Resource     : "
        f"Patient/{fhir_resource_id}"
    )

    print()

    overall_status = "PASS"

    for comparison in comparisons:
        result = status(
            comparison["expected"],
            comparison["actual"],
        )

        if result == "FAIL":
            overall_status = "FAIL"

        failure_domain = (
            None
            if result == "PASS"
            else "DATA_RECONCILIATION"
        )

        diagnostic_message = (
            None
            if result == "PASS"
            else (
                f"Source {comparison['source']} "
                f"expected {comparison['expected']} "
                f"but {comparison['target']} "
                f"contained {comparison['actual']}. "
                f"Investigate the source-to-FHIR "
                f"transformation or persistence path."
            )
        )

        validation_result_id = (
            record_validation_result(
                fhir_lineage_id=fhir_lineage_id,
                validation_category="DATA_RECONCILIATION",
                validation_rule=comparison["rule"],
                validation_status=result,
                source_element=comparison["source"],
                target_element=comparison["target"],
                expected_value=str(
                    comparison["expected"]
                ),
                actual_value=str(
                    comparison["actual"]
                ),
                failure_domain=failure_domain,
                diagnostic_message=diagnostic_message,
                validation_run_id=validation_run_id,
            )
        )

        print(
            f"{comparison['source']:<8}"
            f" -> "
            f"{comparison['target']:<24}"
            f"{result:<6}"
            f" "
            f"(validation_result_id="
            f"{validation_result_id})"
        )

    complete_validation_run(
        validation_run_id=validation_run_id,
        overall_status=overall_status,
    )

    print()
    print(
        f"Overall Status    : "
        f"{overall_status}"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()