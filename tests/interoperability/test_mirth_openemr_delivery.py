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
        "observation_at": "2025-01-16T11:30:00+00:00",
        "received_at": "2026-09-07T00:52:11+00:00",
        "value_type": "NM",
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
    assert scenario["message"]["timestamp"] == "20250116113000"
    assert scenario["order"]["observation_timestamp"] == "20250116113000"

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

def test_oru_audit_preserves_clinical_observation_time():
    migration = open(
        "infrastructure/mirth/interop-db/init/"
        "021-oru-observation-chronology.sql",
        encoding="utf-8",
    ).read()

    channel = open(
        "infrastructure/mirth/channels/ORU_R01_IN.xml",
        encoding="utf-8",
    ).read()

    assert "observation_at TIMESTAMPTZ" in migration
    assert "oru_observation_datetime" in channel
    assert "observation_at" in channel
    assert "YYYYMMDDHH24MISSTZHTZM" in channel
