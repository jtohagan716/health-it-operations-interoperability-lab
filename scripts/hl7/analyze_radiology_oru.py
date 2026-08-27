from __future__ import annotations

import argparse
from pathlib import Path

from scripts.hl7.analyze_oru import (
    ADMINISTRATIVE_SEX_MAP,
    IDENTIFIER_TYPE_MAP,
    RESULT_STATUS_MAP,
    VALUE_TYPE_MAP,
    analyze_oru,
    valid_hl7_timestamp,
    valid_yyyymmdd,
)


RADIOLOGY_VALUE_TYPES = {
    "TX",
    "ST",
}


def analyze_radiology_oru(
    fixture_path: Path | str,
) -> dict:
    """
    Parse an ORU^R01 using the shared ORU parser and apply
    radiology-report-specific validation semantics.
    """

    result = analyze_oru(fixture_path)

    checks = {
        # Patient identity
        "Patient ID present":
            bool(result["patient_id"]),

        "Assigning authority present":
            bool(result["assigning_authority"]),

        "Identifier type is MR":
            result["identifier_type"] == "MR",

        "Family name present":
            bool(result["family_name"]),

        "Given name present":
            bool(result["given_name"]),

        "DOB present":
            bool(result["date_of_birth"]),

        "DOB format is YYYYMMDD":
            valid_yyyymmdd(
                result["date_of_birth"]
            ),

        "Administrative sex recognized":
            result["administrative_sex"]
            in ADMINISTRATIVE_SEX_MAP,

        # Message contract
        "Message type is ORU":
            result["message_code"] == "ORU",

        "Trigger event is R01":
            result["trigger_event"] == "R01",

        "Message structure is ORU_R01":
            result["message_structure"] == "ORU_R01",

        "Message control ID present":
            bool(result["message_control_id"]),

        "HL7 version is 2.5.1":
            result["hl7_version"] == "2.5.1",

        "Receiving application is MIRTH":
            result["receiving_application"]
            == "MIRTH",

        "MSH-7 timestamp valid":
            valid_hl7_timestamp(
                result["message_datetime"]
            ),

        # Radiology order/report identity
        "Placer order number present":
            bool(result["placer_order_number"]),

        "Filler order number present":
            bool(result["filler_order_number"]),

        "Radiology service code present":
            bool(result["service_code"]),

        "Radiology service text present":
            bool(result["service_text"]),

        "Service coding system present":
            bool(result["service_coding_system"]),

        "OBR observation timestamp valid":
            valid_hl7_timestamp(
                result["observation_datetime"]
            ),

        "OBR result status recognized":
            result["obr_result_status"]
            in RESULT_STATUS_MAP,

        "Radiology report is final":
            result["obr_result_status"] == "F",

        # Narrative radiology result
        "Narrative value type recognized":
            result["value_type"]
            in RADIOLOGY_VALUE_TYPES,

        "Radiology observation code present":
            bool(result["observation_code"]),

        "Radiology observation text present":
            bool(result["observation_text"]),

        "Observation coding system present":
            bool(
                result[
                    "observation_coding_system"
                ]
            ),

        "Narrative result present":
            bool(result["observation_value"]),

        "OBX result status recognized":
            result["obx_result_status"]
            in RESULT_STATUS_MAP,

        "Radiology observation is final":
            result["obx_result_status"] == "F",

        "OBR and OBX result status agree":
            result["obr_result_status"]
            == result["obx_result_status"],
    }

    result = dict(result)
    result["checks"] = checks

    return result


def print_radiology_analysis(
    result: dict,
) -> None:
    print()
    print("ORU^R01 RADIOLOGY RESULT ANALYSIS")
    print("--------------------------------")

    print()
    print("MESSAGE / TRANSACTION")
    print(
        "Control ID:          "
        f"{result['message_control_id']}"
    )
    print(
        "Message Type:        "
        f"{result['message_code']}"
        f"^{result['trigger_event']}"
        f"^{result['message_structure']}"
    )
    print(
        "Sending Application: "
        f"{result['sending_application']}"
    )
    print(
        "Receiving App:       "
        f"{result['receiving_application']}"
    )

    print()
    print("PATIENT")
    print(
        "Patient ID:          "
        f"{result['patient_id']}"
    )
    print(
        "Name:                "
        f"{result['given_name']} "
        f"{result['family_name']}"
    )
    print(
        "Identifier Type:     "
        f"{result['identifier_type']} "
        f"({IDENTIFIER_TYPE_MAP.get(result['identifier_type'], 'Unknown')})"
    )

    print()
    print("RADIOLOGY ORDER / REPORT")
    print(
        "Placer Order:        "
        f"{result['placer_order_number']}"
    )
    print(
        "Filler / Accession:  "
        f"{result['filler_order_number']}"
    )
    print(
        "Procedure:           "
        f"{result['service_code']} - "
        f"{result['service_text']}"
    )
    print(
        "Report Status:       "
        f"{result['obr_result_status']} "
        f"({RESULT_STATUS_MAP.get(result['obr_result_status'], 'Unknown')})"
    )

    print()
    print("RADIOLOGY RESULT")
    print(
        "Value Type:          "
        f"{result['value_type']} "
        f"({VALUE_TYPE_MAP.get(result['value_type'], 'Unknown')})"
    )
    print(
        "Observation:         "
        f"{result['observation_code']} - "
        f"{result['observation_text']}"
    )
    print(
        "Impression:          "
        f"{result['observation_value']}"
    )
    print(
        "Result Status:       "
        f"{result['obx_result_status']} "
        f"({RESULT_STATUS_MAP.get(result['obx_result_status'], 'Unknown')})"
    )

    print()
    print("VALIDATION")

    for description, passed in result[
        "checks"
    ].items():
        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{status}: {description}"
        )

    overall = all(
        result["checks"].values()
    )

    print()
    print(
        "OVERALL: "
        + ("PASS" if overall else "FAIL")
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze and validate a synthetic "
            "HL7 ORU^R01 radiology result."
        )
    )

    parser.add_argument(
        "--fixture",
        required=True,
        type=Path,
        help="Path to HL7 radiology ORU fixture.",
    )

    args = parser.parse_args()

    result = analyze_radiology_oru(
        args.fixture
    )

    print_radiology_analysis(
        result
    )


if __name__ == "__main__":
    main()