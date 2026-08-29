from pathlib import Path
import xml.etree.ElementTree as ET


CCDA_PATH = Path(
    "examples/ccda/avery-testpatient-ccd.xml"
)

NS = {
    "cda": "urn:hl7-org:v3",
}

MEDICATION_SECTION_LOINC = "10160-0"

MEDICATION_ACTIVITY_TEMPLATE = (
    "2.16.840.1.113883.10.20.22.4.16"
)

MEDICATION_ACTIVITY_VERSION = "2014-06-09"


def find_medication_section(root: ET.Element) -> ET.Element:
    sections = root.findall(
        ".//cda:structuredBody/cda:component/cda:section",
        NS,
    )

    for section in sections:
        code = section.find("cda:code", NS)

        if (
            code is not None
            and code.attrib.get("code") == MEDICATION_SECTION_LOINC
        ):
            return section

    raise AssertionError("Medication section not found")


def test_medication_activity_uses_expected_template():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_medication_section(root)

    activities = section.findall(
        ".//cda:substanceAdministration",
        NS,
    )

    assert len(activities) == 1

    activity = activities[0]

    template_ids = activity.findall(
        "cda:templateId",
        NS,
    )

    template_pairs = {
        (
            template_id.attrib.get("root"),
            template_id.attrib.get("extension"),
        )
        for template_id in template_ids
    }

    assert (
        MEDICATION_ACTIVITY_TEMPLATE,
        MEDICATION_ACTIVITY_VERSION,
    ) in template_pairs


def test_medication_activity_contains_expected_coded_semantics():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_medication_section(root)

    activity = section.find(
        ".//cda:substanceAdministration",
        NS,
    )

    assert activity is not None

    medication_code = activity.find(
        "cda:consumable/"
        "cda:manufacturedProduct/"
        "cda:manufacturedMaterial/"
        "cda:code",
        NS,
    )

    assert medication_code is not None
    assert medication_code.attrib.get("displayName") == (
        "lisinopril 10 MG Oral Tablet"
    )
    assert medication_code.attrib.get("codeSystemName") == "RXNORM"

    route = activity.find(
        "cda:routeCode",
        NS,
    )

    assert route is not None
    assert route.attrib.get("code") == "C38288"
    assert route.attrib.get("displayName") == "By Mouth"

    dose = activity.find(
        "cda:doseQuantity",
        NS,
    )

    assert dose is not None
    assert dose.attrib.get("value") == "10"
    assert dose.attrib.get("unit") == "mg"