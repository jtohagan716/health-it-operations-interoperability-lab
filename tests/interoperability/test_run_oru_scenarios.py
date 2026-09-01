from pathlib import Path

import pytest

from scripts.hl7.oru_scenario import load_scenario
from scripts.hl7.run_oru_scenarios import (
    assert_persisted_semantics,
    sql_literal,
    wait_for_accepted_observation,
)


SCENARIO_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "hl7"
    / "oru"
    / "scenarios"
)


def test_sql_literal_escapes_single_quotes():
    assert sql_literal("LAB'O1") == "'LAB''O1'"


def test_wait_returns_first_persisted_row(monkeypatch):
    expected = {"processing_status": "ACCEPTED"}
    responses = iter((None, expected))

    monkeypatch.setattr(
        "scripts.hl7.run_oru_scenarios.get_accepted_observation",
        lambda message_control_id: next(responses),
    )
    monkeypatch.setattr(
        "scripts.hl7.run_oru_scenarios.time.sleep",
        lambda interval: None,
    )

    observed = wait_for_accepted_observation(
        "CONTROL-1",
        timeout=1.0,
        interval=0.01,
    )

    assert observed is expected


def test_wait_rejects_nonpositive_timeout():
    with pytest.raises(
        ValueError,
        match="timeout must be positive",
    ):
        wait_for_accepted_observation(
            "CONTROL-1",
            timeout=0,
        )


def test_wait_rejects_nonpositive_interval():
    with pytest.raises(
        ValueError,
        match="interval must be positive",
    ):
        wait_for_accepted_observation(
            "CONTROL-1",
            interval=0,
        )


def test_semantic_mismatch_reports_field():
    normal_scenario = load_scenario(
        SCENARIO_DIRECTORY
        / "normal-glucose-final.json"
    )
    persisted = {
        "patient_identifier": "LAB000001",
        "placer_order_number": "ORD-NORMAL-001",
        "filler_order_number": "RPT-NORMAL-001",
        "service_code": "2345-7",
        "processing_status": "ACCEPTED",
        "observation_code": "2345-7",
        "observation_value": "999",
        "units": "mg/dL",
        "reference_range": "70-99",
        "abnormal_flag": "N",
        "result_status": "F",
    }

    with pytest.raises(
        RuntimeError,
        match="observation_value",
    ):
        assert_persisted_semantics(
            normal_scenario,
            persisted,
        )
