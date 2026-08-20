from pathlib import Path
from datetime import datetime
import argparse


DEFAULT_FIXTURE = Path("fixtures/hl7/adt/adt-a04-lab000001.hl7")


PATIENT_CLASS_MAP = {
    "I": "Inpatient",
    "O": "Outpatient",
    "E": "Emergency",
}

IDENTIFIER_TYPE_MAP = {
    "MR": "Medical Record Number",
}

NAME_TYPE_MAP = {
    "L": "Legal Name",
}

SEX_MAP = {
    "M": "Male",
    "F": "Female",
    "O": "Other",
    "U": "Unknown",
}


def load_segments(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")

    return [
        segment.strip()
        for segment in text.splitlines()
        if segment.strip()
    ]


def get_segment(segments: list[str], segment_name: str) -> str:
    for segment in segments:
        if segment.startswith(f"{segment_name}|"):
            return segment

    raise ValueError(f"Segment {segment_name} not found")


def get_component(components: list[str], index: int) -> str:
    if index < len(components):
        return components[index]

    return ""


def get_field(fields: list[str], index: int) -> str:
    if index < len(fields):
        return fields[index]

    return ""


def is_valid_hl7_timestamp(value: str) -> bool:
    if not value:
        return False

    formats = [
        "%Y%m%d%H%M%S%z",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y%m%d",
    ]

    for fmt in formats:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue

    return False


def analyze_adt(path: Path) -> dict:
    segments = load_segments(path)

    msh = get_segment(segments, "MSH")
    evn = get_segment(segments, "EVN")
    pid = get_segment(segments, "PID")
    pv1 = get_segment(segments, "PV1")

    # ---------------------------------------------------------
    # PID
    # ---------------------------------------------------------

    pid_fields = pid.split("|")

    patient_identifier = get_field(pid_fields, 3)
    identifier_components = patient_identifier.split("^")

    patient_id = get_component(identifier_components, 0)
    assigning_authority = get_component(identifier_components, 3)
    identifier_type = get_component(identifier_components, 4)

    patient_name = get_field(pid_fields, 5)
    name_components = patient_name.split("^")

    family_name = get_component(name_components, 0)
    given_name = get_component(name_components, 1)
    name_type = get_component(name_components, 6)

    date_of_birth = get_field(pid_fields, 7)
    administrative_sex = get_field(pid_fields, 8)

    # ---------------------------------------------------------
    # PV1
    # ---------------------------------------------------------

    pv1_fields = pv1.split("|")

    patient_class = get_field(pv1_fields, 2)

    location_components = get_field(pv1_fields, 3).split("^")

    point_of_care = get_component(location_components, 0)
    room = get_component(location_components, 1)
    bed = get_component(location_components, 2)
    facility = get_component(location_components, 3)

    attending_provider_components = get_field(
        pv1_fields,
        7
    ).split("^")

    attending_provider_id = get_component(
        attending_provider_components,
        0
    )
    attending_provider_family = get_component(
        attending_provider_components,
        1
    )
    attending_provider_given = get_component(
        attending_provider_components,
        2
    )

    visit_number = get_field(pv1_fields, 19)

    # ---------------------------------------------------------
    # MSH
    # ---------------------------------------------------------

    msh_fields = msh.split("|")

    field_separator = "|"
    encoding_characters = get_field(msh_fields, 1)
    sending_application = get_field(msh_fields, 2)
    sending_facility = get_field(msh_fields, 3)
    receiving_application = get_field(msh_fields, 4)
    receiving_facility = get_field(msh_fields, 5)
    message_datetime = get_field(msh_fields, 6)
    message_type = get_field(msh_fields, 8)
    message_control_id = get_field(msh_fields, 9)
    processing_id = get_field(msh_fields, 10)
    hl7_version = get_field(msh_fields, 11)

    message_type_components = message_type.split("^")

    message_code = get_component(message_type_components, 0)
    trigger_event = get_component(message_type_components, 1)
    message_structure = get_component(message_type_components, 2)

    # ---------------------------------------------------------
    # EVN
    # ---------------------------------------------------------

    evn_fields = evn.split("|")

    event_type = get_field(evn_fields, 1)
    event_datetime = get_field(evn_fields, 2)

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    checks = {
        "Patient ID present": bool(patient_id),
        "Assigning authority present": bool(assigning_authority),
        "Identifier type is MR": identifier_type == "MR",
        "Family name present": bool(family_name),
        "Given name present": bool(given_name),
        "Patient name type recognized": name_type in NAME_TYPE_MAP,
        "DOB present": bool(date_of_birth),
        "Patient class recognized": patient_class in PATIENT_CLASS_MAP,
        "Visit number present": bool(visit_number),
        "Message type is ADT": message_code == "ADT",
        "Trigger event is A04": trigger_event == "A04",
        "Message structure is ADT_A01": message_structure == "ADT_A01",
        "Message control ID present": bool(message_control_id),
        "HL7 version is 2.5.1": hl7_version == "2.5.1",
        "Receiving application is MIRTH": receiving_application == "MIRTH",
        "Administrative sex recognized": administrative_sex in SEX_MAP,
        "DOB format is YYYYMMDD":
            len(date_of_birth) == 8 and date_of_birth.isdigit(),
        "EVN event type present": bool(event_type),
        "EVN event type matches MSH trigger event":
            event_type == trigger_event,
        "MSH-7 timestamp valid":
            is_valid_hl7_timestamp(message_datetime),
        "EVN-2 timestamp valid":
            is_valid_hl7_timestamp(event_datetime),
        "EVN-2 matches MSH-7":
            event_datetime == message_datetime,
    }

    return {
        "msh": msh,
        "evn": evn,
        "pid": pid,
        "pv1": pv1,

        "patient_id": patient_id,
        "assigning_authority": assigning_authority,
        "identifier_type": identifier_type,
        "family_name": family_name,
        "given_name": given_name,
        "name_type": name_type,
        "date_of_birth": date_of_birth,
        "administrative_sex": administrative_sex,

        "patient_class": patient_class,
        "point_of_care": point_of_care,
        "room": room,
        "bed": bed,
        "facility": facility,
        "attending_provider_id": attending_provider_id,
        "attending_provider_family": attending_provider_family,
        "attending_provider_given": attending_provider_given,
        "visit_number": visit_number,

        "field_separator": field_separator,
        "encoding_characters": encoding_characters,
        "sending_application": sending_application,
        "sending_facility": sending_facility,
        "receiving_application": receiving_application,
        "receiving_facility": receiving_facility,
        "message_datetime": message_datetime,
        "message_type": message_type,
        "message_control_id": message_control_id,
        "processing_id": processing_id,
        "hl7_version": hl7_version,
        "message_code": message_code,
        "trigger_event": trigger_event,
        "message_structure": message_structure,

        "event_type": event_type,
        "event_datetime": event_datetime,

        "checks": checks,
    }


def print_analysis(result: dict) -> None:
    print("MSH:", result["msh"])
    print("PID:", result["pid"])
    print("PV1:", result["pv1"])
    print("EVN:", result["evn"])

    print("\nPATIENT IDENTITY")
    print(f"Patient ID:          {result['patient_id']}")
    print(f"Assigning Authority: {result['assigning_authority']}")
    print(f"Identifier Type:     {result['identifier_type']}")
    print(f"Family Name:         {result['family_name']}")
    print(f"Given Name:          {result['given_name']}")
    print(f"Name Type:           {result['name_type']}")
    print(f"Date of Birth:       {result['date_of_birth']}")
    print(f"Administrative Sex:  {result['administrative_sex']}")

    print("\nVISIT / ENCOUNTER CONTEXT")
    print(f"Patient Class:       {result['patient_class']}")
    print(f"Point of Care:       {result['point_of_care']}")
    print(f"Room:                {result['room']}")
    print(f"Bed:                 {result['bed']}")
    print(f"Facility:            {result['facility']}")
    print(
        "Attending Provider:  "
        f"{result['attending_provider_id']} - "
        f"{result['attending_provider_family']}, "
        f"{result['attending_provider_given']}"
    )
    print(f"Visit Number:        {result['visit_number']}")

    print("\nCODE INTERPRETATION")
    print(
        f"Patient Class:      "
        f"{result['patient_class']} = "
        f"{PATIENT_CLASS_MAP.get(result['patient_class'], 'Unknown')}"
    )
    print(
        f"Identifier Type:    "
        f"{result['identifier_type']} = "
        f"{IDENTIFIER_TYPE_MAP.get(result['identifier_type'], 'Unknown')}"
    )
    print(
        f"Name Type:          "
        f"{result['name_type']} = "
        f"{NAME_TYPE_MAP.get(result['name_type'], 'Unknown')}"
    )
    print(
        f"Administrative Sex: "
        f"{result['administrative_sex']} = "
        f"{SEX_MAP.get(result['administrative_sex'], 'Unknown')}"
    )

    print("\nMESSAGE HEADER")
    print(
        f"MSH-1 Field Separator:        "
        f"{result['field_separator']}"
    )
    print(
        f"MSH-2 Encoding Characters:   "
        f"{result['encoding_characters']}"
    )
    print(
        f"MSH-3 Sending Application:   "
        f"{result['sending_application']}"
    )
    print(
        f"MSH-4 Sending Facility:      "
        f"{result['sending_facility']}"
    )
    print(
        f"MSH-5 Receiving Application: "
        f"{result['receiving_application']}"
    )
    print(
        f"MSH-6 Receiving Facility:    "
        f"{result['receiving_facility']}"
    )
    print(
        f"MSH-7 Message Date/Time:     "
        f"{result['message_datetime']}"
    )
    print(
        f"MSH-9 Message Type:          "
        f"{result['message_type']}"
    )
    print(
        f"MSH-10 Control ID:           "
        f"{result['message_control_id']}"
    )
    print(
        f"MSH-11 Processing ID:        "
        f"{result['processing_id']}"
    )
    print(
        f"MSH-12 HL7 Version:          "
        f"{result['hl7_version']}"
    )

    print("\nEVENT INFORMATION")
    print(f"EVN-1 Event Type:      {result['event_type']}")
    print(f"EVN-2 Event Date/Time: {result['event_datetime']}")

    print("\nVALIDATION")

    for description, passed in result["checks"].items():
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {description}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze and validate an HL7 v2 ADT message."
    )

    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="Path to the HL7 fixture to analyze.",
    )

    args = parser.parse_args()

    result = analyze_adt(args.fixture)
    print_analysis(result)


if __name__ == "__main__":
    main()