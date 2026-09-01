from pathlib import Path

import pytest

from scripts.hl7.oru_scenario import (
    expected_semantics,
    load_scenario,
)
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


ACCEPTED_SCENARIO_PATHS = tuple(
    path
    for path in sorted(
        SCENARIO_DIRECTORY.glob("*.json")
    )
    if load_scenario(path)["expected"]["ack_code"]
    == "AA"
)


@pytest.mark.parametrize(
    "scenario_path",
    ACCEPTED_SCENARIO_PATHS,
    ids=lambda path: path.stem,
)
def test_oru_scenario_is_accepted_and_persisted(
    scenario_path: Path,
):
    scenario = load_scenario(scenario_path)
    expected = expected_semantics(scenario)
    result = execute_scenario(scenario_path)

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
    for field, value in expected.items():
        assert result.persisted[field] == value
