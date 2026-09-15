from pathlib import Path

from lxml import etree


SOURCE_PATH = Path(
    "examples/ccda/migration/avery-source.xml"
)

XSL_PATH = Path(
    "examples/ccda/migration/source-to-ccda.xsl"
)


NS = {
    "cda": "urn:hl7-org:v3",
}


def transform_source() -> etree._Element:
    source = etree.parse(str(SOURCE_PATH))
    stylesheet = etree.parse(str(XSL_PATH))

    transform = etree.XSLT(stylesheet)

    result = transform(source)

    return result.getroot()


def test_migration_transform_produces_clinical_document():
    root = transform_source()

    assert root.tag == "{urn:hl7-org:v3}ClinicalDocument"


def test_migration_transform_preserves_patient_identity():
    root = transform_source()

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


def test_migration_transform_preserves_medication():
    root = transform_source()

    medication = root.find(
        ".//cda:substanceAdministration",
        NS,
    )

    assert medication is not None

    route = medication.find(
        "cda:routeCode",
        NS,
    )

    dose = medication.find(
        "cda:doseQuantity",
        NS,
    )

    code = medication.find(
        "cda:consumable/"
        "cda:manufacturedProduct/"
        "cda:manufacturedMaterial/"
        "cda:code",
        NS,
    )

    assert route is not None
    assert dose is not None
    assert code is not None

    assert route.attrib["code"] == "C38288"
    assert route.attrib["displayName"] == "By Mouth"

    assert dose.attrib["value"] == "10"
    assert dose.attrib["unit"] == "mg"

    assert (
        code.attrib["displayName"]
        == "lisinopril 10 MG Oral Tablet"
    )

    assert code.attrib["codeSystemName"] == "RXNORM"


def test_migration_transform_preserves_encounters():
    root = transform_source()

    encounters = root.findall(
        ".//cda:encounter",
        NS,
    )

    assert len(encounters) == 2

    descriptions = [
        encounter.find(
            "cda:code",
            NS,
        ).attrib["displayName"]
        for encounter in encounters
    ]

    effective_times = [
        encounter.find(
            "cda:effectiveTime",
            NS,
        ).attrib["value"]
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
