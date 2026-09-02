import argparse
from pathlib import Path

import pytest

from scripts.synthetic.diagnoses import build_payload, build_records, execute, load_profile, render_receiver


def profile():
    return load_profile()


def receiver_source():
    return (Path(__file__).resolve().parents[2] / "scripts" / "synthetic" / "openemr_diagnosis_receiver.php").read_text()


def test_profile_is_restricted_to_synthetic_local_lab():
    value = profile()
    assert value["synthetic_only"] is True
    assert value["environment"] == "local-lab"
    assert value["issue"] == 31


def test_profile_defines_all_ten_cohorts():
    assert len(profile()["cohort_conditions"]) == 10


def test_population_has_one_encounter_diagnosis_per_patient():
    records = build_records(profile())
    assert len(records) == 100
    assert len({row["diagnosis_external_id"] for row in records}) == 100


def test_profile_has_fifty_longitudinal_problems():
    templates = profile()["cohort_conditions"]
    assert sum(10 for value in templates.values() if value["longitudinal_problem"]) == 50


def test_probe_uses_one_patient_that_exercises_both_condition_paths():
    value = profile()
    records = build_records(value, probe=True)
    assert records == [{
        "mrn": "SYNTHMRN000002",
        "problem_external_id": "SYNPRB00000201",
        "diagnosis_external_id": "SYNDX00000201",
        "encounter_external_id": "SYNENC00000201",
    }]


def test_external_identifiers_fit_openemr_column_limit():
    for record in build_records(profile()):
        assert all(len(record[key]) <= 20 for key in (
            "problem_external_id", "diagnosis_external_id", "encounter_external_id"
        ))


@pytest.mark.parametrize("cohort", ["PREDIABETES", "DIABETES", "HYPERTENSION", "CARDIOVASCULAR", "RESPIRATORY"])
def test_chronic_cohorts_have_prior_onset(cohort):
    value = profile()["cohort_conditions"][cohort]
    assert value["longitudinal_problem"] is True
    assert value["onset_days_before"] > 0


@pytest.mark.parametrize("cohort", ["PREVENTIVE", "PEDIATRIC", "OLDER_ADULT", "IDENTITY_EDGE", "RESULT_LIFECYCLE"])
def test_non_chronic_cohorts_do_not_invent_problem_list_conditions(cohort):
    value = profile()["cohort_conditions"][cohort]
    assert value["longitudinal_problem"] is False
    assert value["onset_days_before"] == 0


def test_all_codes_and_titles_are_present():
    for value in profile()["cohort_conditions"].values():
        assert value["code"]
        assert len(value["title"]) >= 2


def test_payload_declares_verify_mode():
    payload = build_payload(profile(), probe=True, verify_only=True)
    assert payload["verify_only"] is True
    assert len(payload["records"]) == 1


def test_receiver_rendering_resolves_all_placeholders():
    template = "payload=__SYNTHETIC_PAYLOAD_BASE64__;commit=__SYNTHETIC_COMMIT__;"
    rendered = render_receiver(template, build_payload(profile(), probe=True), commit=False)
    assert "__SYNTHETIC_" not in rendered
    assert "commit=false" in rendered


def test_commit_requires_exact_environment_and_count():
    with pytest.raises(ValueError, match="environment"):
        execute(probe=True, commit=True, environment="production", confirm_patient_count=1)
    with pytest.raises(ValueError, match="confirm-patient-count 1"):
        execute(probe=True, commit=True, environment="local-lab", confirm_patient_count=100)


def test_parser_style_count_is_integer():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-patient-count", type=int)
    assert parser.parse_args(["--confirm-patient-count", "100"]).confirm_patient_count == 100


def test_receiver_uses_native_condition_and_issue_services():
    source = receiver_source()
    for expected in ("ConditionService", "PatientIssuesService", "linkIssueToEncounter", "sqlBeginTrans", "sqlRollbackTrans"):
        assert expected in source


def test_receiver_does_not_create_billing_rows():
    source = receiver_source().lower()
    assert "insert into billing" not in source
    assert "delete from billing" not in source


def test_receiver_verifies_problem_and_encounter_categories():
    source = receiver_source()
    assert "problem-list-item" in source
    assert "encounter-diagnosis" in source
    assert "Problem-list condition must not have an encounter link" in source


def test_cleanup_is_limited_to_exact_created_relationship():
    source = receiver_source()
    assert "DELETE FROM issue_encounter WHERE pid=? AND list_id=? AND encounter=?" in source
    assert "delete_condition" in source
