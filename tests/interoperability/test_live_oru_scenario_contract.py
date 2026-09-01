from pathlib import Path

import pytest

from scripts.hl7.run_oru_scenarios import (
    execute_scenario,
)


SCENARIO_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "hl7"
    / "oru"
    / "scenarios"
)


@pytest.mark.parametrize(
    "filename,expected_value,expected_flag",
    (
        (
            "normal-glucose-final.json",
            "90",
            "N",
        ),
        (
            "abnormal-glucose-final.json",
            "180",
            "H",
        ),
    ),
)
def test_oru_scenario_is_accepted_and_persisted(
    filename: str,
    expected_value: str,
    expected_flag: str,
):
    result = execute_scenario(
        SCENARIO_DIRECTORY / filename
    )

    assert result.acknowledgment.code == "AA"
    assert (
        result.acknowledgment.control_id
        == result.message_control_id
    )
    assert result.persisted is not None
    assert (
        result.persisted["processing_status"]
        == "ACCEPTED"
    )
    assert (
        result.persisted["observation_value"]
        == expected_value
    )
    assert (
        result.persisted["abnormal_flag"]
        == expected_flag
    )
    assert result.persisted["result_status"] == "F"
