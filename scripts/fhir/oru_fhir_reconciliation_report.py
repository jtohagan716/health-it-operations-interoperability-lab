from __future__ import annotations

from pathlib import Path

from scripts.hl7.analyze_oru import analyze_oru
from scripts.fhir.map_oru_to_observation import (
    map_oru_to_fhir_observation,
)
from scripts.fhir.map_oru_to_diagnostic_report import (
    map_oru_to_fhir_diagnostic_report,
)


HL7_FIXTURE = Path(
    "fixtures/hl7/oru/oru-r01-lab000001.hl7"
)


def build_reconciliation_report() -> dict:
    oru = analyze_oru(HL7_FIXTURE)

    observation = map_oru_to_fhir_observation(
        oru
    )

    observation_reference = (
        "Observation/"
        + observation["identifier"][0]["value"]
    )

    report = map_oru_to_fhir_diagnostic_report(
        oru,
        observation_reference=observation_reference,
    )

    checks = {
        "patient_identity_preserved": (
            observation["subject"]["identifier"]["value"]
            == oru["patient_id"]
            == report["subject"]["identifier"]["value"]
        ),

        "observation_code_preserved": (
            observation["code"]["coding"][0]["code"]
            == oru["observation_code"]
        ),

        "report_code_preserved": (
            report["code"]["coding"][0]["code"]
            == oru["service_code"]
        ),

        "result_value_preserved": (
            observation["valueQuantity"]["value"]
            == float(oru["observation_value"])
        ),

        "units_preserved": (
            observation["valueQuantity"]["unit"]
            == oru["observation_units"]
        ),

        "reference_range_preserved": (
            observation["referenceRange"][0]["text"]
            == oru["reference_range"]
        ),

        "abnormal_flag_preserved": (
            observation["interpretation"][0]
            ["coding"][0]["code"]
            == oru["abnormal_flag"]
        ),

        "report_identifier_preserved": (
            report["identifier"][0]["value"]
            == oru["filler_order_number"]
        ),

        "order_identifier_preserved": (
            report["basedOn"][0]
            ["identifier"]["value"]
            == oru["placer_order_number"]
        ),

        "diagnostic_report_links_observation": (
            report["result"][0]["reference"]
            == observation_reference
        ),
    }

    return {
        "source_control_id": (
            oru["message_control_id"]
        ),
        "patient_id": (
            oru["patient_id"]
        ),
        "placer_order_number": (
            oru["placer_order_number"]
        ),
        "filler_order_number": (
            oru["filler_order_number"]
        ),
        "observation_code": (
            oru["observation_code"]
        ),
        "observation_text": (
            oru["observation_text"]
        ),
        "observation_value": (
            oru["observation_value"]
        ),
        "observation_units": (
            oru["observation_units"]
        ),
        "abnormal_flag": (
            oru["abnormal_flag"]
        ),
        "observation_status": (
            oru["obx_result_status"]
        ),
        "fhir_observation_reference": (
            observation_reference
        ),
        "checks": checks,
        "passed": all(
            checks.values()
        ),
    }


def main() -> None:
    result = build_reconciliation_report()

    print()
    print("ORU -> FHIR RECONCILIATION REPORT")
    print("---------------------------------")

    print(
        f"Source Control ID:   "
        f"{result['source_control_id']}"
    )

    print(
        f"Patient ID:          "
        f"{result['patient_id']}"
    )

    print(
        f"Placer Order:        "
        f"{result['placer_order_number']}"
    )

    print(
        f"Filler Order:        "
        f"{result['filler_order_number']}"
    )

    print(
        f"Observation:         "
        f"{result['observation_code']} - "
        f"{result['observation_text']}"
    )

    print(
        f"Result:              "
        f"{result['observation_value']} "
        f"{result['observation_units']}"
    )

    print(
        f"Abnormal Flag:       "
        f"{result['abnormal_flag']}"
    )

    print(
        f"Result Status:       "
        f"{result['observation_status']}"
    )

    print(
        f"FHIR Observation:    "
        f"{result['fhir_observation_reference']}"
    )

    print()
    print("RECONCILIATION CHECKS")
    print("---------------------")

    for name, passed in result[
        "checks"
    ].items():
        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{status}: {name}"
        )

    print()
    print(
        "OVERALL: "
        + (
            "PASS"
            if result["passed"]
            else "FAIL"
        )
    )


if __name__ == "__main__":
    main()