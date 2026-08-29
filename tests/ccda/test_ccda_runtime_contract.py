import xml.etree.ElementTree as ET
from pathlib import Path


CCDA_PATH = Path("examples/ccda/avery-testpatient-ccd.xml")

NS = {
    "cda": "urn:hl7-org:v3",
}


def load_root() -> ET.Element:
    return ET.parse(CCDA_PATH).getroot()


def test_ccda_is_parseable_and_has_clinical_document_root():
    root = load_root()

    assert root.tag == "{urn:hl7-org:v3}ClinicalDocument"


def test_ccda_contains_expected_patient_identity():
    root = load_root()

    given = root.find(
        ".//cda:recordTarget/"
        "cda:patientRole/"
        "cda:patient/"
        "cda:name/"
        "cda:given",
        NS,
    )

    family = root.find(
        ".//cda:recordTarget/"
        "cda:patientRole/"
        "cda:patient/"
        "cda:name/"
        "cda:family",
        NS,
    )

    birth_time = root.find(
        ".//cda:recordTarget/"
        "cda:patientRole/"
        "cda:patient/"
        "cda:birthTime",
        NS,
    )

    assert given is not None
    assert family is not None
    assert birth_time is not None

    assert given.text == "Avery"
    assert family.text == "Testpatient"
    assert birth_time.attrib["value"] == "19800115"


def test_ccda_contains_expected_medication():
    root = load_root()

    medication = root.find(".//cda:substanceAdministration", NS)

    assert medication is not None

    medication_code = medication.find(
        "cda:consumable/"
        "cda:manufacturedProduct/"
        "cda:manufacturedMaterial/"
        "cda:code",
        NS,
    )

    route = medication.find("cda:routeCode", NS)
    dose = medication.find("cda:doseQuantity", NS)

    assert medication_code is not None
    assert route is not None
    assert dose is not None

    assert medication_code.attrib["displayName"] == "lisinopril 10 MG Oral Tablet"
    assert medication_code.attrib["codeSystemName"] == "RXNORM"

    assert route.attrib["code"] == "C38288"
    assert route.attrib["displayName"] == "By Mouth"

    assert dose.attrib["value"] == "10"
    assert dose.attrib["unit"] == "mg"


def test_ccda_contains_two_expected_encounters():
    root = load_root()

    encounters = root.findall(".//cda:encounter", NS)

    assert len(encounters) == 2

    descriptions = [
        encounter.find("cda:code", NS).attrib["displayName"]
        for encounter in encounters
    ]

    effective_times = [
        encounter.find("cda:effectiveTime", NS).attrib["value"]
        for encounter in encounters
    ]

    assert (
        "Office Visit | Routine office visit - synthetic interoperability lab encounter"
        in descriptions
    )

    assert (
        "Established Patient | Persistent cough"
        in descriptions
    )

    assert "202608132322+0000" in effective_times
    assert "202608251544+0000" in effective_times

def test_semantically_invalid_medication_route_is_detected():
    invalid_path = Path(
        "tests/ccda/fixtures/avery-testpatient-invalid-route.xml"
    )

    root = ET.parse(invalid_path).getroot()

    medication = root.find(".//cda:substanceAdministration", NS)

    assert medication is not None

    route = medication.find("cda:routeCode", NS)

    assert route is not None

    expected_route_code = "C38288"

    assert route.attrib["code"] != expected_route_code