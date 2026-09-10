import copy
from pathlib import Path

import pytest

from scripts.hl7.oru_scenario import (
    build_oru_segments,
    expected_observations,
    expected_semantics,
    load_scenario,
    observations_for_scenario,
    validate_scenario,
)


PANEL_PATH = Path(
    "fixtures/hl7/oru/panels/basic-metabolic-subset-final.json"
)
LEGACY_PATH = Path(
    "fixtures/hl7/oru/scenarios/normal-glucose-final.json"
)


def test_legacy_singular_observation_is_normalized():
    scenario = load_scenario(LEGACY_PATH)

    observations = observations_for_scenario(scenario)

    assert len(observations) == 1
    assert observations[0]["code"] == "2345-7"


def test_panel_builds_one_ordered_obx_per_observation():
    scenario = load_scenario(PANEL_PATH)

    segments = build_oru_segments(scenario)
    obx_segments = [
        segment for segment in segments if segment.startswith("OBX|")
    ]

    assert len(obx_segments) == 4
    assert [segment.split("|")[1] for segment in obx_segments] == [
        "1", "2", "3", "4"
    ]
    assert [segment.split("|")[3].split("^")[0] for segment in obx_segments] == [
        "2345-7", "3094-0", "2160-0", "2951-2"
    ]
    assert [segment.split("|")[5] for segment in obx_segments] == [
        "90", "14", "0.9", "140"
    ]


def test_panel_expected_observations_preserve_order_and_values():
    scenario = load_scenario(PANEL_PATH)

    expected = expected_observations(scenario)

    assert [item["observation_code"] for item in expected] == [
        "2345-7", "3094-0", "2160-0", "2951-2"
    ]
    assert [item["observation_value"] for item in expected] == [
        "90", "14", "0.9", "140"
    ]


def test_panel_declares_honest_local_service_terminology():
    scenario = load_scenario(PANEL_PATH)

    obr = next(
        segment
        for segment in build_oru_segments(scenario)
        if segment.startswith("OBR|")
    )

    assert obr.split("|")[4] == (
        "SYN-CHEM-4^Synthetic chemistry four-analyte panel^L"
    )


def test_scenario_rejects_both_singular_and_plural_forms():
    scenario = load_scenario(PANEL_PATH)
    scenario["observation"] = copy.deepcopy(scenario["observations"][0])

    with pytest.raises(ValueError, match="exactly one"):
        validate_scenario(scenario)


def test_scenario_rejects_empty_observation_collection():
    scenario = load_scenario(PANEL_PATH)
    scenario["observations"] = []

    with pytest.raises(ValueError, match="non-empty list"):
        validate_scenario(scenario)


def test_scenario_reports_indexed_panel_validation_errors():
    scenario = load_scenario(PANEL_PATH)
    del scenario["observations"][1]["units"]

    with pytest.raises(ValueError, match=r"observations\[1\]\.units"):
        validate_scenario(scenario)


def test_legacy_flat_semantics_refuse_to_hide_panel_members():
    scenario = load_scenario(PANEL_PATH)

    with pytest.raises(ValueError, match="expected_observations"):
        expected_semantics(scenario)
