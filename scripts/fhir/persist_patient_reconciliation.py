from scripts.fhir.patient_helpers import (
    extract_fhir_identifier,
    get_fhir_patient_with_timing,
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

    fhir_patient, patient_search_duration_ms = (
        get_fhir_patient_with_timing(
            hl7_patient["identifier"]
        )
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
        scenario_name="patient_identity_reconciliation",
        synthetic=False,
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
            "actual": fhir_patient.get(
                "birthDate"
            ),
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
    print("PERSISTING FHIR PATIENT VALIDATION EVIDENCE")
    print("=" * 72)

    print(
        f"Transaction ID        : "
        f"{transaction_id}"
    )

    print(
        f"FHIR Lineage ID       : "
        f"{fhir_lineage_id}"
    )

    print(
        f"Validation Run ID     : "
        f"{validation_run_id}"
    )

    print(
        f"FHIR Resource         : "
        f"Patient/{fhir_resource_id}"
    )

    print(
        f"Patient Search Latency: "
        f"{patient_search_duration_ms:.3f} ms"
    )

    print()

    overall_status = "PASS"

    #
    # Runtime validation evidence
    #
    runtime_validation_result_id = (
        record_validation_result(
            fhir_lineage_id=fhir_lineage_id,
            validation_category="FHIR_RUNTIME",
            validation_rule=(
                "FHIR Patient identifier search succeeds"
            ),
            validation_status="PASS",
            source_element="Patient?identifier",
            target_element="FHIR Bundle -> Patient",
            expected_value=hl7_patient["identifier"],
            actual_value=fhir_identifier,
            failure_domain=None,
            diagnostic_message=None,
            duration_ms=patient_search_duration_ms,
            validation_run_id=validation_run_id,
        )
    )

    print(
        f"{'FHIR API':<8}"
        f" -> "
        f"{'Patient identifier search':<24}"
        f"{'PASS':<6}"
        f" "
        f"({patient_search_duration_ms:.3f} ms, "
        f"validation_result_id="
        f"{runtime_validation_result_id})"
    )

    #
    # Source-to-FHIR reconciliation evidence
    #
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
                f"Expected "
                f"{comparison['expected']} "
                f"but observed "
                f"{comparison['actual']}. "
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
                duration_ms=None,
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
        f"Overall Status        : "
        f"{overall_status}"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()