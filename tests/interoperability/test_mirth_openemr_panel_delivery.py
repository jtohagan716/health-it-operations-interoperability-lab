from pathlib import Path

from scripts.hl7.openemr_oru_ingest import (
    OpenEmrTarget,
    build_openemr_oru_segments,
)
from scripts.hl7.mirth_openemr_delivery import (
    scenario_from_delivery,
)
from scripts.hl7.oru_scenario import load_scenario


PANEL_PATH = Path(
    "fixtures/hl7/oru/panels/"
    "basic-metabolic-subset-final.json"
)
TARGET = OpenEmrTarget(
    order_id=9001,
    patient_id=1,
    encounter_id=4,
    lab_id=2,
)


def panel_delivery_row():
    return {
        "oru_message_id": 155,
        "message_control_id": "SCENARIO-ORU-PANEL-001",
        "sending_application": "LABSYSTEM",
        "sending_facility": "INTEROPLAB",
        "patient_identifier": "LAB000001",
        "patient_family_name": "Testpatient",
        "patient_given_name": "Avery",
        "patient_date_of_birth": "19800115",
        "patient_administrative_sex": "M",
        "placer_order_number": "ORD-SCENARIO-PANEL-001",
        "filler_order_number": "LABRPT-SCENARIO-PANEL-001",
        "service_code": "SYN-CHEM-4",
        "service_text": "Synthetic chemistry four-analyte panel",
        "obr_result_status": "F",
        "observation_at": "2026-09-09T18:45:00-04:00",
        "received_at": "2026-09-10T16:12:21-04:00",
        "observations": [
            {
                "sequence": 1,
                "obx_set_id": "1",
                "value_type": "NM",
                "code": "2345-7",
                "display": "Glucose",
                "value": "90",
                "units": "mg/dL",
                "reference_range": "70-99",
                "abnormal_flag": "N",
                "result_status": "F",
            },
            {
                "sequence": 2,
                "obx_set_id": "2",
                "value_type": "NM",
                "code": "3094-0",
                "display": "Urea nitrogen",
                "value": "14",
                "units": "mg/dL",
                "reference_range": "7-20",
                "abnormal_flag": "N",
                "result_status": "F",
            },
            {
                "sequence": 3,
                "obx_set_id": "3",
                "value_type": "NM",
                "code": "2160-0",
                "display": "Creatinine",
                "value": "0.9",
                "units": "mg/dL",
                "reference_range": "0.6-1.3",
                "abnormal_flag": "N",
                "result_status": "F",
            },
            {
                "sequence": 4,
                "obx_set_id": "4",
                "value_type": "NM",
                "code": "2951-2",
                "display": "Sodium",
                "value": "140",
                "units": "mmol/L",
                "reference_range": "135-145",
                "abnormal_flag": "N",
                "result_status": "F",
            },
        ],
    }


def test_panel_delivery_preserves_all_ordered_observations():
    scenario = scenario_from_delivery(panel_delivery_row())

    assert "observation" not in scenario
    assert len(scenario["observations"]) == 4
    assert [
        observation["code"]
        for observation in scenario["observations"]
    ] == [
        "2345-7",
        "3094-0",
        "2160-0",
        "2951-2",
    ]
    assert [
        observation["value"]
        for observation in scenario["observations"]
    ] == ["90", "14", "0.9", "140"]


def test_worker_aggregates_observations_in_canonical_order():
    text = open(
        "scripts/hl7/mirth_openemr_delivery.py",
        encoding="utf-8",
    ).read()

    assert "json_agg" in text
    assert "observation_sequence" in text
    assert "oru_observation_id" in text


def test_worker_records_dynamic_result_count():
    text = open(
        "scripts/hl7/mirth_openemr_delivery.py",
        encoding="utf-8",
    ).read()

    assert '"result_count": len(' in text
    assert 'scenario["observations"]' in text


def test_openemr_adapter_timestamps_every_panel_obx():
    scenario = load_scenario(PANEL_PATH)
    segments = build_openemr_oru_segments(
        scenario,
        TARGET,
        message_control_id="OPENEMR-PANEL-CONTROL",
        filler_id="OPENEMR-PANEL-FILLER",
        commit=False,
    )

    obx_segments = [
        segment.split("|")
        for segment in segments
        if segment.startswith("OBX|")
    ]

    assert len(obx_segments) == 4
    assert {
        fields[14]
        for fields in obx_segments
    } == {
        scenario["order"]["observation_timestamp"]
    }


def test_receiver_enforces_exact_panel_cardinality():
    text = open(
        "scripts/hl7/openemr_oru_receiver.php",
        encoding="utf-8",
    ).read()

    assert (
        "$expectedResultCount = "
        "__OPENEMR_EXPECTED_RESULT_COUNT__;"
    ) in text
    assert (
        "$afterResults !== "
        "$beforeResults + $expectedResultCount"
    ) in text
    assert "count($persistedResults)" in text
    assert "'persisted_results' => $persistedResults" in text


def test_ingest_renders_expected_panel_result_count():
    text = open(
        "scripts/hl7/openemr_oru_ingest.py",
        encoding="utf-8",
    ).read()

    assert "__OPENEMR_EXPECTED_RESULT_COUNT__" in text
    assert 'segment.startswith("OBX|")' in text
