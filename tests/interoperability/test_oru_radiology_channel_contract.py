from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHANNEL_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "channels"
    / "ORU_R01_IN.xml"
)


def channel_text() -> str:
    return CHANNEL_PATH.read_text(encoding="utf-8")


def test_channel_classifies_narrative_radiology_result():
    text = channel_text()

    assert "isRadiologyNarrative" in text
    assert "serviceCodingSystem == &quot;99INTEROP&quot;" in text
    assert "observations.length == 1" in text
    assert "firstObservation.value_type == &quot;TX&quot;" in text
    assert "firstObservation.code == &quot;IMPRESSION&quot;" in text
    assert (
        "firstObservation.coding_system == "
        "&quot;99INTEROP&quot;"
    ) in text


def test_radiology_narrative_bypasses_numeric_lab_requirements():
    text = channel_text()

    assert text.count("!isRadiologyNarrative") >= 5
    assert "OBX units present" in text
    assert "OBX reference range present" in text
    assert "OBX abnormal flag recognized" in text


def test_radiology_narrative_requires_final_statuses():
    text = channel_text()

    assert "Radiology OBR status is final" in text
    assert "Radiology OBX status is final" in text


def test_existing_laboratory_and_panel_policies_remain_present():
    text = channel_text()

    assert "OBR coding system is LOINC" in text
    assert "OBX coding system is LOINC" in text
    assert "SYN-CHEM-4 required member present" in text
    assert "OBR and OBX observation codes agree" in text
