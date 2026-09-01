import json
from pathlib import Path

import pytest

from scripts.hl7.analyze_oru import analyze_oru
from scripts.hl7.oru_scenario import (
    build_oru_segments,
    expected_semantics,
    load_scenario,
    validate_scenario,
)
from scripts.hl7.send_mllp import (
    get_message_control_id,
)


SCENARIO_DIRECTORY = Path(
    "fixtures/hl7/oru/scenarios"
)

SCENARIO_PATHS = tuple(
    sorted(
        SCENARIO_DIRECTORY.glob("*.json")
    )
)


@pytest.mark.parametrize(
    "scenario_path",
    SCENARIO_PATHS,
    ids=lambda path: path.stem,
)
def test_scenario_builds_valid_oru_message(
    scenario_path: Path,
    tmp_path: Path,
):
    scenario = load_scenario(scenario_path)

    segments = build_oru_segments(scenario)

    fixture = tmp_path / f"{scenario['scenario_id']}.hl7"
    fixture.write_text(
        "\n".join(segments) + "\n",
        encoding="utf-8",
    )

    analysis = analyze_oru(fixture)

    failed_checks = [
        description
        for description, passed
        in analysis["checks"].items()
        if not passed
    ]

    assert failed_checks == []


@pytest.mark.parametrize(
    "scenario_path",
    SCENARIO_PATHS,
    ids=lambda path: path.stem,
)
def test_scenario_expected_semantics_match_generated_message(
    scenario_path: Path,
    tmp_path: Path,
):
    scenario = load_scenario(scenario_path)

    segments = build_oru_segments(scenario)

    fixture = tmp_path / "generated.hl7"
    fixture.write_text(
        "\n".join(segments) + "\n",
        encoding="utf-8",
    )

    analysis = analyze_oru(fixture)
    expected = expected_semantics(scenario)

    observed = {
        "patient_identifier": analysis["patient_id"],
        "placer_order_number": analysis[
            "placer_order_number"
        ],
        "filler_order_number": analysis[
            "filler_order_number"
        ],
        "service_code": analysis["service_code"],
        "observation_code": analysis[
            "observation_code"
        ],
        "observation_value": analysis[
            "observation_value"
        ],
        "units": analysis["observation_units"],
        "reference_range": analysis[
            "reference_range"
        ],
        "abnormal_flag": analysis["abnormal_flag"],
        "result_status": analysis[
            "obx_result_status"
        ],
    }

    assert observed == expected


def test_runtime_control_id_can_override_scenario_default():
    scenario = load_scenario(
        SCENARIO_DIRECTORY
        / "normal-glucose-final.json"
    )

    segments = build_oru_segments(
        scenario,
        message_control_id="RUNTIME-CONTROL-ID",
    )

    assert (
        get_message_control_id(segments)
        == "RUNTIME-CONTROL-ID"
    )


def test_scenarios_have_unique_ids():
    scenario_ids = {
        load_scenario(path)["scenario_id"]
        for path in SCENARIO_PATHS
    }

    assert len(scenario_ids) == len(SCENARIO_PATHS)


def test_missing_required_field_is_rejected():
    scenario = load_scenario(
        SCENARIO_DIRECTORY
        / "normal-glucose-final.json"
    )

    del scenario["observation"]["units"]

    with pytest.raises(
        ValueError,
        match="observation.units",
    ):
        validate_scenario(scenario)


def test_invalid_ack_expectation_is_rejected():
    scenario = load_scenario(
        SCENARIO_DIRECTORY
        / "normal-glucose-final.json"
    )

    scenario["expected"]["ack_code"] = "XX"

    with pytest.raises(
        ValueError,
        match="AA, AE, or AR",
    ):
        validate_scenario(scenario)


def test_non_object_json_is_rejected(tmp_path: Path):
    path = tmp_path / "invalid-scenario.json"
    path.write_text(
        json.dumps(["not", "an", "object"]),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="must be a JSON object",
    ):
        load_scenario(path)
