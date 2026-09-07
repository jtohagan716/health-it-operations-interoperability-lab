import argparse
from pathlib import Path

import pytest

from scripts.synthetic.laboratory_orders import (
    build_payload,
    build_records,
    execute,
    load_profile,
    render_receiver,
)


def profile():
    return load_profile()


def receiver_source():
    return (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "synthetic"
        / "openemr_laboratory_order_receiver.php"
    ).read_text(encoding="utf-8")


def test_profile_is_restricted_to_synthetic_local_lab():
    value = profile()
    assert value["synthetic_only"] is True
    assert value["environment"] == "local-lab"
    assert value["issue"] == 31
    assert value["patient_count"] == 100


def test_phase_has_one_requisition_and_line_per_patient():
    value = profile()
    assert value["requisitions_per_patient"] == 1
    assert value["phase_targets"]["requisitions"] == 100
    assert value["phase_targets"]["ordered_test_lines"] == 100


def test_future_population_targets_remain_explicit():
    targets = profile()["phase_targets"]
    assert targets["future_ordered_test_lines"] == 450
    assert targets["future_result_observations"] == 500


def test_full_population_has_100_unique_requisitions():
    records = build_records(profile())
    assert len(records) == 100
    assert len({row["mrn"] for row in records}) == 100
    assert len({row["order_external_id"] for row in records}) == 100


def test_records_use_first_existing_historical_encounter():
    records = build_records(profile())
    assert records[0]["encounter_external_id"] == "SYNENC00000101"
    assert records[-1]["encounter_external_id"] == "SYNENC00010001"
    assert {row["encounter_sequence"] for row in records} == {1}


def test_order_identifiers_are_stable_and_fit_openemr_limit():
    records = build_records(profile())
    assert records[0]["order_external_id"] == "SYNLAB00000101"
    assert records[-1]["order_external_id"] == "SYNLAB00010001"
    assert records == build_records(profile())
    assert all(len(row["order_external_id"]) <= 20 for row in records)


def test_probe_is_one_glucose_requisition_for_first_patient():
    assert build_records(profile(), probe=True) == [
        {
            "mrn": "SYNTHMRN000001",
            "encounter_external_id": "SYNENC00000101",
            "order_external_id": "SYNLAB00000101",
            "encounter_sequence": 1,
        }
    ]


def test_orderable_uses_loinc_glucose_code():
    orderable = profile()["orderable"]
    assert orderable["procedure_code"] == "2345-7"
    assert orderable["standard_code"] == "2345-7"
    assert orderable["units"] == "mg/dL"
    assert orderable["range"] == "70-99"


def test_local_laboratory_is_vendor_neutral_and_has_no_npi():
    laboratory = profile()["laboratory"]
    assert laboratory["recv_app_id"] == "SYNLIS"
    assert "DORN" not in str(laboratory).upper()
    assert "npi" not in laboratory


def test_payload_separates_patient_requisition_and_line_counts():
    full = build_payload(profile(), verify_only=True)
    probe = build_payload(profile(), probe=True, verify_only=True)
    assert full["expected_patients"] == 100
    assert full["expected_requisitions"] == 100
    assert full["expected_order_lines"] == 100
    assert probe["expected_patients"] == 1
    assert probe["expected_requisitions"] == 1
    assert probe["expected_order_lines"] == 1
    assert probe["verify_only"] is True


def test_receiver_rendering_resolves_all_placeholders():
    template = (
        "payload=__SYNTHETIC_PAYLOAD_BASE64__;"
        "commit=__SYNTHETIC_COMMIT__;"
    )
    rendered = render_receiver(
        template,
        build_payload(profile(), probe=True),
        commit=False,
    )
    assert "__SYNTHETIC_" not in rendered
    assert "commit=false" in rendered


def test_commit_requires_exact_environment_and_patient_count():
    with pytest.raises(ValueError, match="environment"):
        execute(
            probe=True,
            commit=True,
            environment="production",
            confirm_patient_count=1,
        )
    with pytest.raises(ValueError, match="confirm-patient-count 1"):
        execute(
            probe=True,
            commit=True,
            environment="local-lab",
            confirm_patient_count=100,
        )


def test_parser_style_count_is_integer():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-patient-count", type=int)
    assert (
        parser.parse_args(
            ["--confirm-patient-count", "100"]
        ).confirm_patient_count
        == 100
    )


def test_receiver_uses_openemr_order_save_boundaries():
    source = receiver_source()
    for expected in (
        "library/forms.inc.php",
        "procedure_order_save_functions.php",
        "insertProcedureOrderCode",
        "UuidRegistry::createMissingUuidsForTables",
        "addForm",
    ):
        assert expected in source


def test_receiver_requires_persisted_patient_encounter_and_diagnosis():
    source = receiver_source()
    assert "p.usertext1='SYNTHETIC_POPULATION_V1'" in source
    assert "'synthetic encounter'" in source
    assert 'Expected exactly one {$label}' in source
    assert "Synthetic encounter diagnosis is required" in source


def test_receiver_has_transaction_and_compensating_cleanup():
    source = receiver_source()
    for expected in (
        "sqlBeginTrans",
        "sqlCommitTrans",
        "sqlRollbackTrans",
        "compensating_cleanup",
    ):
        assert expected in source


def test_receiver_verifies_order_line_and_form_registration():
    source = receiver_source()
    assert "Laboratory ordered-test postcondition mismatch" in source
    assert "laboratory order form registration" in source
    assert "formdir='procedure_order'" in source


def test_receiver_does_not_transmit_or_create_results_or_billing():
    source = receiver_source().lower()
    for forbidden in (
        "connectorapi::sendorder",
        "insert into procedure_report",
        "insert into procedure_result",
        "insert into billing",
    ):
        assert forbidden not in source


def test_cleanup_is_scoped_to_exact_created_orders():
    source = receiver_source()
    assert "DELETE FROM procedure_order WHERE procedure_order_id=?" in source
    assert "DELETE FROM procedure_order_code WHERE procedure_order_id=?" in source
    assert "DELETE FROM forms WHERE formdir='procedure_order'" in source
