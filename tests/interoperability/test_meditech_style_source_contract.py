from pathlib import Path

from scripts.hl7.oru_scenario import (
    build_oru_segments,
    load_scenario,
)


SCENARIO_PATH = Path(
    "fixtures/hl7/oru/scenarios/"
    "meditech-expanse-style-glucose-final.json"
)


def test_meditech_style_source_metadata_is_preserved():
    scenario = load_scenario(SCENARIO_PATH)

    segments = build_oru_segments(scenario)
    msh_fields = segments[0].split("|")

    assert msh_fields[2] == "MEDITECH-EXPANSE-SIM"
    assert msh_fields[3] == "SYNTHETIC-HOSPITAL-SIM"
    assert msh_fields[8] == "ORU^R01^ORU_R01"
    assert msh_fields[11] == "2.5.1"

def test_meditech_style_oru_preserves_patient_order_and_result():
    scenario = load_scenario(SCENARIO_PATH)
    segments = build_oru_segments(scenario)

    pid = next(s.split("|") for s in segments if s.startswith("PID|"))
    obr = next(s.split("|") for s in segments if s.startswith("OBR|"))
    obx = [s.split("|") for s in segments if s.startswith("OBX|")]

    assert pid[3].split("^")[0] == "MEDI000001"
    assert pid[5].split("^")[:2] == ["Synthetic", "Patient"]

    assert obr[2] == "ORD-MEDITECH-SIM-001"
    assert obr[3] == "LAB-MEDITECH-SIM-001"
    assert obr[4].split("^")[:2] == ["2345-7", "Glucose"]
    assert obr[25] == "F"

    assert len(obx) == 1
    assert obx[0][3].split("^")[:2] == ["2345-7", "Glucose"]
    assert obx[0][5] == "92"
    assert obx[0][6] == "mg/dL"
    assert obx[0][7] == "70-99"
    assert obx[0][8] == "N"
    assert obx[0][11] == "F"