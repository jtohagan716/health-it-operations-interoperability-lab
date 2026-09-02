import argparse
from pathlib import Path

import pytest

from scripts.synthetic.encounter_vitals import build_payload, build_records, execute, load_profile, render_receiver


def profile():
    return load_profile()


def test_profile_is_restricted_to_synthetic_local_lab():
    value = profile()
    assert value["synthetic_only"] is True
    assert value["environment"] == "local-lab"
    assert value["issue"] == 31


def test_full_population_has_exactly_one_record_per_patient():
    records = build_records(profile())
    assert len(records) == 100
    assert len({row["mrn"] for row in records}) == 100


def test_identifiers_are_stable_and_within_openemr_column_limit():
    records = build_records(profile())
    assert records[0]["mrn"] == "SYNTHMRN000001"
    assert records[-1]["mrn"] == "SYNTHMRN000100"
    assert records[0]["encounter_external_id"] == "SYNENC00000101"
    assert records[-1]["vitals_external_id"] == "SYNVIT00010001"
    assert all(len(row["encounter_external_id"]) <= 20 for row in records)
    assert all(len(row["vitals_external_id"]) <= 20 for row in records)


def test_probe_contains_only_first_golden_patient():
    records = build_records(profile(), probe=True)
    assert [row["mrn"] for row in records] == ["SYNTHMRN000001"]


def test_dates_are_deterministic_and_historical():
    first = build_records(profile())[0]
    again = build_records(profile())[0]
    assert first == again
    assert first["encounter_at"].startswith("2025-")
    assert first["vitals_at"] > first["encounter_at"]


def test_all_population_cohorts_have_templates():
    expected = {"PREVENTIVE", "PREDIABETES", "DIABETES", "HYPERTENSION", "CARDIOVASCULAR", "RESPIRATORY", "PEDIATRIC", "OLDER_ADULT", "IDENTITY_EDGE", "RESULT_LIFECYCLE"}
    assert set(profile()["cohort_defaults"]) == expected


@pytest.mark.parametrize("cohort", ["PREVENTIVE", "DIABETES", "HYPERTENSION", "RESPIRATORY", "PEDIATRIC", "OLDER_ADULT"])
def test_vital_templates_are_numeric_and_positive(cohort):
    vital = profile()["cohort_defaults"][cohort]
    for field in ("bps", "bpd", "weight", "height", "temperature", "pulse", "respiration", "oxygen_saturation"):
        assert isinstance(vital[field], (int, float))
        assert vital[field] > 0


def test_payload_declares_verify_mode():
    payload = build_payload(profile(), probe=True, verify_only=True)
    assert payload["verify_only"] is True
    assert len(payload["records"]) == 1


def test_receiver_rendering_resolves_all_placeholders():
    template = "payload=__SYNTHETIC_PAYLOAD_BASE64__;commit=__SYNTHETIC_COMMIT__;"
    rendered = render_receiver(template, build_payload(profile(), probe=True), commit=False)
    assert "__SYNTHETIC_" not in rendered
    assert "commit=false" in rendered


def test_commit_requires_exact_environment_and_count(monkeypatch):
    with pytest.raises(ValueError, match="environment"):
        execute(probe=True, commit=True, environment="production", confirm_patient_count=1)
    with pytest.raises(ValueError, match="confirm-patient-count 1"):
        execute(probe=True, commit=True, environment="local-lab", confirm_patient_count=100)


def test_parser_style_count_is_integer():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-patient-count", type=int)
    assert parser.parse_args(["--confirm-patient-count", "100"]).confirm_patient_count == 100


def test_receiver_uses_native_services_and_recovery_guards():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "synthetic" / "openemr_encounter_vitals_receiver.php").read_text()
    for expected in ("insertEncounter", "insertVital", "FormVitals", "sqlBeginTrans", "sqlCommitTrans", "sqlRollbackTrans", "compensating_cleanup"):
        assert expected in source


def test_receiver_verifies_both_form_registrations():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "synthetic" / "openemr_encounter_vitals_receiver.php").read_text()
    assert "formdir='newpatient'" in source
    assert "formdir='vitals'" in source


def test_receiver_establishes_background_execution_identity():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "synthetic" / "openemr_encounter_vitals_receiver.php").read_text()
    assert "authUserID" in source
    assert "SessionWrapperFactory" in source


def test_vitals_correlation_does_not_depend_on_filtered_external_id():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "synthetic" / "openemr_encounter_vitals_receiver.php").read_text()
    assert "Deterministic synthetic historical vitals ' . $record['vitals_external_id']" in source
    assert "FROM forms f JOIN form_vitals v" in source


def test_native_form_registration_id_is_diagnostic_not_authoritative():
    source = (Path(__file__).resolve().parents[2] / "scripts" / "synthetic" / "openemr_encounter_vitals_receiver.php").read_text()
    assert "native_vitals_form_id" in source
    assert "(int)$vitals['form_registration_id'] !==" not in source
    assert 'DELETE FROM forms WHERE id=? AND formdir=\'vitals\'' not in source
    assert "DELETE FROM forms WHERE formdir='vitals' AND form_id=? AND pid=? AND encounter=?" in source
