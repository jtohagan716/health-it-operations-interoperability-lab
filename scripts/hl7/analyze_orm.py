from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


DEFAULT_FIXTURE = Path(
    "fixtures/hl7/orm/orm-o01-rad000001.hl7"
)


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


ORDER_CONTROL_MAP = {
    "NW": "New Order",
}


ORDER_STATUS_MAP = {
    "SC": "In Process / Scheduled",
    "IP": "In Process",
    "CM": "Completed",
    "DC": "Discontinued",
    "HD": "On Hold",
    "RP": "Replaced",
}


def load_segments(
    path: Path,
) -> list[str]:
    text = path.read_text(
        encoding="utf-8-sig"
    )

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def get_segment(
    segments: list[str],
    segment_name: str,
) -> str:
    for segment in segments:
        if segment.startswith(
            segment_name + "|"
        ):
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


def valid_hl7_timestamp(
    value: str,
) -> bool:
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
            continue

    return False


def valid_yyyymmdd(
    value: str,
) -> bool:
    if len(value) != 8:
        return False

    try:
        datetime.strptime(
            value,
            "%Y%m%d",
        )

        return True

    except ValueError:
        return False


def analyze_orm(
    fixture_path: Path | str,
) -> dict:
    """
    Analyze a synthetic HL7 ORM^O01 General Order Message
    representing a radiology/imaging order.
    """

    fixture_path = Path(
        fixture_path
    )

    segments = load_segments(
        fixture_path
    )

    msh = get_segment(
        segments,
        "MSH",
    )

    pid = get_segment(
        segments,
        "PID",
    )

    pv1 = get_segment(
        segments,
        "PV1",
    )

    orc = get_segment(
        segments,
        "ORC",
    )

    obr = get_segment(
        segments,
        "OBR",
    )

    # ---------------------------------------------------------
    # MSH - Message Header
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
    # PID - Patient Identity
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
    # PV1 - Encounter Context
    # ---------------------------------------------------------

    patient_class = get_field(
        pv1,
        2,
    )

    visit_number = get_field(
        pv1,
        19,
    )

    # ---------------------------------------------------------
    # ORC - Common Order
    # ---------------------------------------------------------

    order_control = get_field(
        orc,
        1,
    )

    orc_placer_order_number = get_field(
        orc,
        2,
    )

    orc_filler_order_number = get_field(
        orc,
        3,
    )

    order_status = get_field(
        orc,
        5,
    )

    transaction_datetime = get_field(
        orc,
        9,
    )

    ordering_provider_field = get_field(
        orc,
        12,
    )

    ordering_provider_id = get_component(
        ordering_provider_field,
        1,
    )

    ordering_provider_family = get_component(
        ordering_provider_field,
        2,
    )

    ordering_provider_given = get_component(
        ordering_provider_field,
        3,
    )

    # ---------------------------------------------------------
    # OBR - Observation Request / Imaging Procedure
    # ---------------------------------------------------------

    obr_placer_order_number = get_field(
        obr,
        2,
    )

    obr_filler_order_number = get_field(
        obr,
        3,
    )

    obr_4 = get_field(
        obr,
        4,
    )

    procedure_code = get_component(
        obr_4,
        1,
    )

    procedure_text = get_component(
        obr_4,
        2,
    )

    procedure_coding_system = get_component(
        obr_4,
        3,
    )

    # ---------------------------------------------------------
    # Lab interface contract
    # ---------------------------------------------------------
    #
    # For this synthetic radiology workflow, the filler order
    # identifier is deliberately used as the imaging accession
    # identifier that will later be matched to the DICOM
    # AccessionNumber.
    #
    # This is a documented lab contract, not an assertion that
    # every real-world HL7 implementation maps accession numbers
    # this way.
    # ---------------------------------------------------------

    accession_number = (
        obr_filler_order_number
    )

    # ---------------------------------------------------------
    # Validation
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

        "DOB format is YYYYMMDD":
            valid_yyyymmdd(
                date_of_birth
            ),

        "Administrative sex recognized":
            administrative_sex
            in ADMINISTRATIVE_SEX_MAP,

        "Patient class recognized":
            patient_class
            in PATIENT_CLASS_MAP,

        "Visit number present":
            bool(visit_number),

        "Message type is ORM":
            message_code == "ORM",

        "Trigger event is O01":
            trigger_event == "O01",

        "Message structure is ORM_O01":
            message_structure == "ORM_O01",

        "Message control ID present":
            bool(message_control_id),

        "HL7 version is 2.5.1":
            hl7_version == "2.5.1",

        "Receiving application is MIRTH":
            receiving_application
            == "MIRTH",

        "MSH-7 timestamp valid":
            valid_hl7_timestamp(
                message_datetime
            ),

        "Order control is NW":
            order_control == "NW",

        "ORC placer order number present":
            bool(
                orc_placer_order_number
            ),

        "ORC filler order number present":
            bool(
                orc_filler_order_number
            ),

        "Order status recognized":
            order_status
            in ORDER_STATUS_MAP,

        "ORC transaction timestamp valid":
            valid_hl7_timestamp(
                transaction_datetime
            ),

        "Ordering provider ID present":
            bool(
                ordering_provider_id
            ),

        "Ordering provider family name present":
            bool(
                ordering_provider_family
            ),

        "Ordering provider given name present":
            bool(
                ordering_provider_given
            ),

        "OBR placer order number present":
            bool(
                obr_placer_order_number
            ),

        "OBR filler order number present":
            bool(
                obr_filler_order_number
            ),

        "ORC and OBR placer order numbers agree":
            (
                orc_placer_order_number
                == obr_placer_order_number
            ),

        "ORC and OBR filler order numbers agree":
            (
                orc_filler_order_number
                == obr_filler_order_number
            ),

        "Procedure code present":
            bool(procedure_code),

        "Procedure description present":
            bool(procedure_text),

        "Procedure coding system present":
            bool(
                procedure_coding_system
            ),

        "Accession number present":
            bool(accession_number),
    }

    return {
        "fixture":
            str(fixture_path),

        "msh":
            msh,

        "pid":
            pid,

        "pv1":
            pv1,

        "orc":
            orc,

        "obr":
            obr,

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

        "patient_class":
            patient_class,

        "visit_number":
            visit_number,

        "order_control":
            order_control,

        "orc_placer_order_number":
            orc_placer_order_number,

        "orc_filler_order_number":
            orc_filler_order_number,

        "order_status":
            order_status,

        "transaction_datetime":
            transaction_datetime,

        "ordering_provider_id":
            ordering_provider_id,

        "ordering_provider_family":
            ordering_provider_family,

        "ordering_provider_given":
            ordering_provider_given,

        "obr_placer_order_number":
            obr_placer_order_number,

        "obr_filler_order_number":
            obr_filler_order_number,

        "accession_number":
            accession_number,

        "procedure_code":
            procedure_code,

        "procedure_text":
            procedure_text,

        "procedure_coding_system":
            procedure_coding_system,

        "checks":
            checks,
    }


def print_analysis(
    result: dict,
) -> None:
    print()
    print(
        "HL7 ORM^O01 GENERAL ORDER MESSAGE"
    )
    print(
        "RADIOLOGY / IMAGING ORDER ANALYSIS"
    )
    print(
        "----------------------------------"
    )

    print()
    print("MESSAGE")
    print(
        f"Control ID:          "
        f"{result['message_control_id']}"
    )
    print(
        f"Message Type:        "
        f"{result['message_code']}^"
        f"{result['trigger_event']}^"
        f"{result['message_structure']}"
    )
    print(
        f"Sending Application: "
        f"{result['sending_application']}"
    )
    print(
        f"Receiving App:       "
        f"{result['receiving_application']}"
    )

    print()
    print("PATIENT")
    print(
        f"Patient ID:          "
        f"{result['patient_id']}"
    )
    print(
        f"Patient Name:        "
        f"{result['given_name']} "
        f"{result['family_name']}"
    )
    print(
        f"Visit Number:        "
        f"{result['visit_number']}"
    )

    print()
    print("IMAGING ORDER")
    print(
        f"Order Control:       "
        f"{result['order_control']} "
        f"({ORDER_CONTROL_MAP.get(result['order_control'], 'Unknown')})"
    )
    print(
        f"Placer Order:        "
        f"{result['orc_placer_order_number']}"
    )
    print(
        f"Filler Order:        "
        f"{result['orc_filler_order_number']}"
    )
    print(
        f"Accession Number:    "
        f"{result['accession_number']}"
    )
    print(
        f"Order Status:        "
        f"{result['order_status']} "
        f"({ORDER_STATUS_MAP.get(result['order_status'], 'Unknown')})"
    )
    print(
        f"Procedure:           "
        f"{result['procedure_code']} - "
        f"{result['procedure_text']}"
    )
    print(
        f"Coding System:       "
        f"{result['procedure_coding_system']}"
    )
    print(
        "Ordering Provider:   "
        f"{result['ordering_provider_id']} - "
        f"{result['ordering_provider_family']}, "
        f"{result['ordering_provider_given']}"
    )

    print()
    print("ORDER IDENTITY")
    print(
        f"ORC Placer:          "
        f"{result['orc_placer_order_number']}"
    )
    print(
        f"OBR Placer:          "
        f"{result['obr_placer_order_number']}"
    )
    print(
        f"ORC Filler:          "
        f"{result['orc_filler_order_number']}"
    )
    print(
        f"OBR Filler:          "
        f"{result['obr_filler_order_number']}"
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

    print()
    print(
        "OVERALL: "
        + (
            "PASS"
            if all(
                result["checks"].values()
            )
            else "FAIL"
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze and validate a synthetic "
            "HL7 ORM^O01 General Order Message "
            "representing a radiology order."
        )
    )

    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=(
            "Path to the HL7 ORM^O01 "
            "General Order Message fixture."
        ),
    )

    args = parser.parse_args()

    result = analyze_orm(
        args.fixture
    )

    print_analysis(
        result
    )


if __name__ == "__main__":
    main()