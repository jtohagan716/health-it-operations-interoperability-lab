import argparse

import pytest

from scripts.hl7.mirth_openemr_delivery import (
    register_target,
    scenario_from_delivery,
    sql_literal,
)


def sample_row():
    return {
        "oru_message_id": 21, "message_control_id": "LAB-21",
        "sending_application": "LABSYSTEM", "sending_facility": "INTEROPLAB",
        "patient_identifier": "LAB000001", "patient_family_name": "Testpatient",
        "patient_given_name": "Avery", "patient_date_of_birth": "19800115",
        "patient_administrative_sex": "M", "placer_order_number": "4",
        "filler_order_number": "LAB-ORDER-4-RESULT-001", "service_code": "2345-7",
        "service_text": "Glucose", "obr_result_status": "F",
        "received_at": "2026-09-01T22:30:00+00:00", "value_type": "NM",
        "observation_code": "2345-7", "observation_text": "Glucose",
        "observation_value": "90", "units": "mg/dL", "reference_range": "70-99",
        "abnormal_flag": "N", "result_status": "F",
    }


def test_sql_literal_escapes_quotes():
    assert sql_literal("O'Brien") == "'O''Brien'"


def test_delivery_row_becomes_valid_scenario():
    scenario = scenario_from_delivery(sample_row())
    assert scenario["order"]["placer_number"] == "4"
    assert scenario["order"]["filler_number"] == "LAB-ORDER-4-RESULT-001"
    assert scenario["observation"]["value"] == "90"
    assert scenario["patient"]["identifier"] == "LAB000001"


def test_registration_requires_exact_order_confirmation(monkeypatch):
    args = argparse.Namespace(order_id=4, confirm_order_id=3)
    with pytest.raises(ValueError, match="matching Order ID 4"):
        register_target(args)


def test_schema_has_delivery_guards():
    text = open(
        "infrastructure/mirth/interop-db/init/018-openemr-oru-delivery.sql",
        encoding="utf-8",
    ).read()
    assert "oru_message_id BIGINT NOT NULL UNIQUE" in text
    assert "FOR EACH ROW" in text
    assert "NEW.processing_status <> 'ACCEPTED'" in text
    assert "PENDING', 'IN_PROGRESS', 'DELIVERED', 'FAILED" in text
    assert "uq_openemr_oru_active_order" in text
    assert ") ON CONFLICT DO NOTHING" in text


def test_worker_waits_for_observation_before_claiming():
    text = open(
        "scripts/hl7/mirth_openemr_delivery.py",
        encoding="utf-8",
    ).read()
    assert "EXISTS (" in text
    assert "FROM audit.oru_observations o" in text
