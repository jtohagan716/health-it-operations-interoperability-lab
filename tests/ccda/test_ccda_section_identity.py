from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.ccda.extract_section import (
    find_section_by_loinc_and_template,
)


CCDA_PATH = Path(
    "examples/ccda/avery-testpatient-ccd.xml"
)

MEDICATION_LOINC = "10160-0"

MEDICATION_TEMPLATE = (
    "2.16.840.1.113883.10.20.22.2.1.1"
)

WRONG_TEMPLATE = (
    "2.16.840.1.113883.10.20.22.999.999"
)


def test_medication_section_matches_loinc_and_template():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        MEDICATION_TEMPLATE,
    )

    assert section is not None


def test_correct_loinc_with_wrong_template_is_rejected():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        WRONG_TEMPLATE,
    )

    assert section is None

MISLEADING_TITLE_CCDA = Path(
    "tests/ccda/fixtures/"
    "avery-testpatient-misleading-medication-title.xml"
)


def test_medication_section_does_not_depend_on_display_title():
    root = ET.parse(MISLEADING_TITLE_CCDA).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        MEDICATION_TEMPLATE,
    )

    assert section is not None

    ns = {
        "cda": "urn:hl7-org:v3",
    }

    title = section.find("cda:title", ns)

    assert title is not None
    assert title.text == "Banana Inventory"

INVALID_LOINC_CCDA = Path(
    "tests/ccda/fixtures/avery-testpatient-invalid-medication-loinc.xml"
)


def test_correct_title_does_not_override_wrong_loinc():
    root = ET.parse(INVALID_LOINC_CCDA).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        MEDICATION_TEMPLATE,
    )

    assert section is None


def test_invalid_loinc_fixture_still_looks_like_medications_to_human():
    root = ET.parse(INVALID_LOINC_CCDA).getroot()

    ns = {"cda": "urn:hl7-org:v3"}

    sections = root.findall(
        ".//cda:structuredBody/cda:component/cda:section",
        ns,
    )

    medication_like_section = None

    for section in sections:
        title = section.find("cda:title", ns)

        if title is not None and title.text == "History of medication use":
            medication_like_section = section
            break

    assert medication_like_section is not None

    code = medication_like_section.find("cda:code", ns)

    assert code is not None
    assert code.attrib.get("code") == "99999-9"

MEDICATION_TEMPLATE_VERSION = "2014-06-09"
WRONG_MEDICATION_TEMPLATE_VERSION = "2099-01-01"

def test_medication_section_matches_template_family():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        MEDICATION_TEMPLATE,
    )

    assert section is not None


def test_medication_section_matches_specific_template_version():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        MEDICATION_TEMPLATE,
        MEDICATION_TEMPLATE_VERSION,
    )

    assert section is not None


def test_medication_section_rejects_wrong_template_version():
    root = ET.parse(CCDA_PATH).getroot()

    section = find_section_by_loinc_and_template(
        root,
        MEDICATION_LOINC,
        MEDICATION_TEMPLATE,
        WRONG_MEDICATION_TEMPLATE_VERSION,
    )

    assert section is None