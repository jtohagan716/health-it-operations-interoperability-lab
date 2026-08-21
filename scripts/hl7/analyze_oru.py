from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


PATIENT_CLASS_MAP = {
    "I": "Inpatient",
    "O": "Outpatient",
    "E": "Emergency",
}

ADMINISTRATIVE_SEX_MAP = {
    "M": "Male",
    "F": "Female",
    "O": "Other",
    "U": "Unknown",
}

IDENTIFIER_TYPE_MAP = {
    "MR": "Medical Record Number",
}

NAME_TYPE_MAP = {
    "L": "Legal Name",
}

RESULT_STATUS_MAP = {
    "F": "Final",
    "P": "Preliminary",
    "C": "Corrected",
    "I": "Pending",
    "X": "Cancelled",
}

ABNORMAL_FLAG_MAP = {
    "H": "High",
    "L": "Low",
    "HH": "Critical High",
    "LL": "Critical Low",
    "N": "Normal",
}

VALUE_TYPE_MAP = {
    "NM": "Numeric",
    "ST": "String",
    "TX": "Text",
    "CE": "Coded Entry",
    "CWE": "Coded With Exceptions",
}


def get_segment(
    segments: list[str],
    segment_name: str,
) -> str:
    for segment in segments:
        if segment.startswith(segment_name + "|"):
            return segment

    raise ValueError(
        f"Segment {segment_name} not found"
    )


def get_field(
    segment: str,
    field_number: int,
) -> str:
    fields = segment.split("|")

    if field_number >= len(fields):
        return ""

    return fields[field_number]


def get_component(
    field: str,
    component_number: int,
) -> str:
    components = field.split("^")

    index = component_number - 1

    if index >= len(components):
        return ""

    return components[index]


def valid_hl7_timestamp(value: str) -> bool:
    if not value:
        return False

    formats = [
        "%Y%m%d%H%M%S%z",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y%m%d",
    ]

    for format_string in formats:
        try:
            datetime.strptime(
                value,
                format_string,
            )
            return True
        except ValueError:
            pass

    return False


def valid_yyyymmdd(value: str) -> bool:
    if len(value) != 8:
        return False

    try:
        datetime.strptime(value, "%Y%m%d")
        return True
    except ValueError:
        return False


def numeric_value(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def analyze_oru(
    fixture_path: Path | str,
) -> dict:
    fixture_path = Path(fixture_path)

    message = fixture_path.read_text(
        encoding="utf-8-sig"
    )

    segments = [
        line.strip()
        for line in message.splitlines()
        if line.strip()
    ]

    msh = get_segment(
        segments,
        "MSH",
    )

    pid = get_segment(
        segments,
        "PID",
    )

    obr = get_segment(
        segments,
        "OBR",
    )

    obx = get_segment(
        segments,
        "OBX",
    )

    # ---------------------------------------------------------
    # MSH
    # ---------------------------------------------------------

    sending_application = get_field(
        msh,
        2,
    )

    sending_facility = get_field(
        msh,
        3,
    )

    receiving_application = get_field(
        msh,
        4,
    )

    receiving_facility = get_field(
        msh,
        5,
    )

    message_datetime = get_field(
        msh,
        6,
    )

    msh_9 = get_field(
        msh,
        8,
    )

    message_code = get_component(
        msh_9,
        1,
    )

    trigger_event = get_component(
        msh_9,
        2,
    )

    message_structure = get_component(
        msh_9,
        3,
    )

    message_control_id = get_field(
        msh,
        9,
    )

    processing_id = get_field(
        msh,
        10,
    )

    hl7_version = get_field(
        msh,
        11,
    )

    # ---------------------------------------------------------
    # PID
    # ---------------------------------------------------------

    pid_3 = get_field(
        pid,
        3,
    )

    patient_id = get_component(
        pid_3,
        1,
    )

    assigning_authority = get_component(
        pid_3,
        4,
    )

    identifier_type = get_component(
        pid_3,
        5,
    )

    pid_5 = get_field(
        pid,
        5,
    )

    family_name = get_component(
        pid_5,
        1,
    )

    given_name = get_component(
        pid_5,
        2,
    )

    name_type = get_component(
        pid_5,
        7,
    )

    date_of_birth = get_field(
        pid,
        7,
    )

    administrative_sex = get_field(
        pid,
        8,
    )

    # ---------------------------------------------------------
    # OBR
    # ---------------------------------------------------------

    placer_order_number = get_field(
        obr,
        2,
    )

    filler_order_number = get_field(
        obr,
        3,
    )

    obr_4 = get_field(
        obr,
        4,
    )

    service_code = get_component(
        obr_4,
        1,
    )

    service_text = get_component(
        obr_4,
        2,
    )

    service_coding_system = get_component(
        obr_4,
        3,
    )

    observation_datetime = get_field(
        obr,
        7,
    )

    obr_result_status = get_field(
        obr,
        25,
    )

    # ---------------------------------------------------------
    # OBX
    # ---------------------------------------------------------

    obx_set_id = get_field(
        obx,
        1,
    )

    value_type = get_field(
        obx,
        2,
    )

    obx_3 = get_field(
        obx,
        3,
    )

    observation_code = get_component(
        obx_3,
        1,
    )

    observation_text = get_component(
        obx_3,
        2,
    )

    observation_coding_system = get_component(
        obx_3,
        3,
    )

    observation_value = get_field(
        obx,
        5,
    )

    observation_units = get_field(
        obx,
        6,
    )

    reference_range = get_field(
        obx,
        7,
    )

    abnormal_flag = get_field(
        obx,
        8,
    )

    obx_result_status = get_field(
        obx,
        11,
    )

    # ---------------------------------------------------------
    # Interface-contract validation
    # ---------------------------------------------------------

    checks = {
        "Patient ID present":
            bool(patient_id),

        "Assigning authority present":
            bool(assigning_authority),

        "Identifier type is MR":
            identifier_type == "MR",

        "Family name present":
            bool(family_name),

        "Given name present":
            bool(given_name),

        "Patient name type recognized":
            name_type in NAME_TYPE_MAP,

        "DOB present":
            bool(date_of_birth),

        "DOB format is YYYYMMDD":
            valid_yyyymmdd(date_of_birth),

        "Administrative sex recognized":
            administrative_sex
            in ADMINISTRATIVE_SEX_MAP,

        "Message type is ORU":
            message_code == "ORU",

        "Trigger event is R01":
            trigger_event == "R01",

        "Message structure is ORU_R01":
            message_structure == "ORU_R01",

        "Message control ID present":
            bool(message_control_id),

        "HL7 version is 2.5.1":
            hl7_version == "2.5.1",

        "Receiving application is MIRTH":
            receiving_application == "MIRTH",

        "MSH-7 timestamp valid":
            valid_hl7_timestamp(
                message_datetime
            ),

        "Placer order number present":
            bool(placer_order_number),

        "Filler order number present":
            bool(filler_order_number),

        "OBR service code present":
            bool(service_code),

        "OBR coding system is LOINC":
            service_coding_system == "LN",

        "OBR observation timestamp valid":
            valid_hl7_timestamp(
                observation_datetime
            ),

        "OBR result status recognized":
            obr_result_status
            in RESULT_STATUS_MAP,

        "OBX value type recognized":
            value_type
            in VALUE_TYPE_MAP,

        "OBX observation code present":
            bool(observation_code),

        "OBX coding system is LOINC":
            observation_coding_system
            == "LN",

        "OBX observation value present":
            bool(observation_value),

        "Numeric OBX contains numeric value":
            (
                value_type != "NM"
                or numeric_value(
                    observation_value
                )
            ),

        "OBX units present":
            bool(observation_units),

        "OBX reference range present":
            bool(reference_range),

        "OBX abnormal flag recognized":
            abnormal_flag
            in ABNORMAL_FLAG_MAP,

        "OBX result status recognized":
            obx_result_status
            in RESULT_STATUS_MAP,

        "OBR and OBX observation codes agree":
            service_code
            == observation_code,

        "OBR and OBX result status agree":
            obr_result_status
            == obx_result_status,
    }

    return {
        "fixture": str(fixture_path),
        "msh": msh,
        "pid": pid,
        "obr": obr,
        "obx": obx,

        "sending_application":
            sending_application,

        "sending_facility":
            sending_facility,

        "receiving_application":
            receiving_application,

        "receiving_facility":
            receiving_facility,

        "message_datetime":
            message_datetime,

        "message_code":
            message_code,

        "trigger_event":
            trigger_event,

        "message_structure":
            message_structure,

        "message_control_id":
            message_control_id,

        "processing_id":
            processing_id,

        "hl7_version":
            hl7_version,

        "patient_id":
            patient_id,

        "assigning_authority":
            assigning_authority,

        "identifier_type":
            identifier_type,

        "family_name":
            family_name,

        "given_name":
            given_name,

        "name_type":
            name_type,

        "date_of_birth":
            date_of_birth,

        "administrative_sex":
            administrative_sex,

        "placer_order_number":
            placer_order_number,

        "filler_order_number":
            filler_order_number,

        "service_code":
            service_code,

        "service_text":
            service_text,

        "service_coding_system":
            service_coding_system,

        "observation_datetime":
            observation_datetime,

        "obr_result_status":
            obr_result_status,

        "obx_set_id":
            obx_set_id,

        "value_type":
            value_type,

        "observation_code":
            observation_code,

        "observation_text":
            observation_text,

        "observation_coding_system":
            observation_coding_system,

        "observation_value":
            observation_value,

        "observation_units":
            observation_units,

        "reference_range":
            reference_range,

        "abnormal_flag":
            abnormal_flag,

        "obx_result_status":
            obx_result_status,

        "checks":
            checks,
    }


def print_analysis(
    result: dict,
) -> None:
    print()
    print("ORU^R01 LAB RESULT ANALYSIS")
    print("--------------------------")

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
        "Sending Facility:    "
        f"{result['sending_facility']}"
    )
    print(
        "Receiving App:       "
        f"{result['receiving_application']}"
    )
    print(
        "Message Date/Time:   "
        f"{result['message_datetime']}"
    )

    print()
    print("PATIENT")
    print(
        "Patient ID:          "
        f"{result['patient_id']}"
    )
    print(
        "Assigning Authority: "
        f"{result['assigning_authority']}"
    )
    print(
        "Identifier Type:     "
        f"{result['identifier_type']} "
        f"({IDENTIFIER_TYPE_MAP.get(result['identifier_type'], 'Unknown')})"
    )
    print(
        "Name:                "
        f"{result['given_name']} "
        f"{result['family_name']}"
    )
    print(
        "DOB:                 "
        f"{result['date_of_birth']}"
    )
    print(
        "Administrative Sex:  "
        f"{result['administrative_sex']} "
        f"({ADMINISTRATIVE_SEX_MAP.get(result['administrative_sex'], 'Unknown')})"
    )

    print()
    print("ORDER / REPORT")
    print(
        "Placer Order:        "
        f"{result['placer_order_number']}"
    )
    print(
        "Filler Order:        "
        f"{result['filler_order_number']}"
    )
    print(
        "Service:             "
        f"{result['service_code']} - "
        f"{result['service_text']}"
    )
    print(
        "Coding System:       "
        f"{result['service_coding_system']}"
    )
    print(
        "Observation Time:    "
        f"{result['observation_datetime']}"
    )
    print(
        "Report Status:       "
        f"{result['obr_result_status']} "
        f"({RESULT_STATUS_MAP.get(result['obr_result_status'], 'Unknown')})"
    )

    print()
    print("OBSERVATION")
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
        "Result:              "
        f"{result['observation_value']} "
        f"{result['observation_units']}"
    )
    print(
        "Reference Range:     "
        f"{result['reference_range']}"
    )
    print(
        "Abnormal Flag:       "
        f"{result['abnormal_flag']} "
        f"({ABNORMAL_FLAG_MAP.get(result['abnormal_flag'], 'Unknown')})"
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze and validate a synthetic "
            "HL7 ORU^R01 laboratory result."
        )
    )

    parser.add_argument(
        "--fixture",
        required=True,
        type=Path,
        help="Path to HL7 ORU fixture.",
    )

    args = parser.parse_args()

    result = analyze_oru(
        args.fixture
    )

    print_analysis(
        result
    )


if __name__ == "__main__":
    main()