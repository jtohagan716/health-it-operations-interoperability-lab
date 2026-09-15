import xml.etree.ElementTree as ET
from pathlib import Path


SOURCE_PATH = Path(
    "examples/ccda/migration/avery-source.xml"
)


def load_source() -> ET.Element:
    return ET.parse(SOURCE_PATH).getroot()


def test_migration_source_is_parseable():
    root = load_source()

    assert root.tag == "MigrationSource"


def test_migration_source_preserves_patient_identity():
    root = load_source()

    patient = root.find("Patient")

    assert patient is not None
    assert patient.findtext("Given") == "Avery"
    assert patient.findtext("Family") == "Testpatient"
    assert patient.findtext("BirthDate") == "19800115"

    sex = patient.find("AdministrativeSex")

    assert sex is not None
    assert sex.attrib["code"] == "M"
    assert sex.text == "Male"


def test_migration_source_preserves_medication_semantics():
    root = load_source()

    medication = root.find("./Medications/Medication")

    assert medication is not None

    assert (
        medication.findtext("DisplayName")
        == "lisinopril 10 MG Oral Tablet"
    )

    assert medication.findtext("CodeSystemName") == "RXNORM"

    route = medication.find("Route")
    dose = medication.find("Dose")

    assert route is not None
    assert dose is not None

    assert route.attrib["code"] == "C38288"
    assert route.text == "By Mouth"

    assert dose.attrib["unit"] == "mg"
    assert dose.text == "10"


def test_migration_source_preserves_encounter_set():
    root = load_source()

    encounters = root.findall("./Encounters/Encounter")

    assert len(encounters) == 2

    descriptions = [
        encounter.findtext("Description")
        for encounter in encounters
    ]

    effective_times = [
        encounter.findtext("EffectiveTime")
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
