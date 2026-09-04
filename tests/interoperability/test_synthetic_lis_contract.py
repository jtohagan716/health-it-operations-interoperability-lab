from scripts.hl7.oml_order import LaboratoryOrder, build_oml_segments
from scripts.hl7.synthetic_lis import deterministic_glucose, scenario_from_order


def test_oml_preserves_order_patient_and_encounter_identity():
    order = LaboratoryOrder(
        placer_order_number="SYNLAB00000101",
        patient_identifier="SYNTHMRN000001",
        patient_family_name="Example",
        patient_given_name="Patient",
        patient_date_of_birth="19800101",
        patient_sex="F",
        visit_number="12",
        service_code="2345-7",
        service_text="Glucose",
        ordered_at="2025-01-15 10:00:00",
        order_id=6, patient_id=1, encounter_id=5, lab_id=4,
    )
    segments = build_oml_segments(order, control_id="SYNLIS-OML-000001")
    assert segments[0].split("|")[8] == "OML^O21^OML_O21"
    assert "SYNTHMRN000001^^^INTEROPLAB^MR" in segments[1]
    assert segments[2].split("|")[19] == "12"
    assert segments[3].split("|")[2] == "SYNLAB00000101"
    assert segments[4].split("|")[4] == "2345-7^Glucose^LN"


def test_glucose_generation_is_deterministic_and_in_range():
    first = deterministic_glucose("SYNTHMRN000001")
    second = deterministic_glucose("SYNTHMRN000001")
    assert first == second
    assert 82 <= int(first[0]) <= 98
    assert first[1] == "N"


def test_result_reuses_placer_and_assigns_stable_filler():
    row = {
        "lis_order_id": 1,
        "patient_identifier": "SYNTHMRN000001",
        "patient_family_name": "Example",
        "patient_given_name": "Patient",
        "patient_date_of_birth": "19800101",
        "patient_administrative_sex": "F",
        "placer_order_number": "SYNLAB00000101",
        "filler_order_number": "SYNLIS-SYNLAB00000101",
        "service_code": "2345-7",
        "service_text": "Glucose",
        "received_at": "2025-01-15T10:00:00+00:00",
    }
    scenario = scenario_from_order(row)
    assert scenario["order"]["placer_number"] == "SYNLAB00000101"
    assert scenario["order"]["filler_number"] == "SYNLIS-SYNLAB00000101"
    assert scenario["message"]["control_id"] == "SYNLIS-ORU-000001-01"
