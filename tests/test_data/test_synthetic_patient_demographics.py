import argparse
import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.synthetic.patient_demographics import (
    APPROVED_ENVIRONMENT,
    PatientDemographicsError,
    build_manifest,
    build_patients,
    load_profile,
    select_probe,
    validate_commit_confirmation,
)


def generated():
    profile = load_profile()
    return profile, build_patients(profile)


def test_generates_exact_patient_and_golden_counts():
    _, patients = generated()
    assert len(patients) == 100
    assert sum(patient["golden_patient"] for patient in patients) == 10


def test_identifiers_and_logical_keys_are_unique_and_deterministic():
    _, first = generated()
    _, second = generated()
    assert first == second
    assert len({p["patient_id"] for p in first}) == 100
    assert len({p["logical_key"] for p in first}) == 100
    assert first[0]["patient_id"] == "SYNTHMRN000001"
    assert first[-1]["patient_id"] == "SYNTHMRN000100"


def test_each_cohort_has_ten_patients_and_golden_set_spans_all_cohorts():
    profile, patients = generated()
    counts = Counter(patient["cohort_codes"][0] for patient in patients)
    assert counts == Counter({cohort: 10 for cohort in profile["cohorts"]})
    assert {patient["cohort_codes"][0] for patient in patients[:10]} == set(profile["cohorts"])


def test_provider_assignments_are_balanced():
    _, patients = generated()
    counts = Counter(patient["provider_username"] for patient in patients)
    assert len(counts) == 25
    assert set(counts.values()) == {4}


def test_demographic_values_use_openemr_option_ids():
    profile, patients = generated()
    assert {p["administrative_sex"] for p in patients} == {"Male", "Female"}
    assert {p["race"] for p in patients} <= set(profile["race_distribution"])
    assert {p["ethnicity"] for p in patients} <= set(profile["ethnicity_distribution"])
    assert {p["language"] for p in patients} <= set(profile["language_distribution"])
    assert {p["marital_status"] for p in patients} <= set(profile["marital_distribution"])


def test_contact_values_are_safe_and_unique():
    _, patients = generated()
    assert len({p["phone"] for p in patients}) == 100
    assert len({p["email"] for p in patients}) == 100
    assert all(p["phone"].startswith("716-555-01") for p in patients)
    assert all(p["email"].endswith("@example.invalid") for p in patients)
    assert all("ss" not in p and "drivers_license" not in p for p in patients)


def test_identity_edge_cohort_contains_five_near_duplicate_pairs():
    _, patients = generated()
    edge = [p for p in patients if p["cohort_codes"] == ["IDENTITY_EDGE"]]
    identities = Counter((p["given_name"], p["family_name"], p["birth_date"]) for p in edge)
    assert len(edge) == 10
    assert len(identities) == 5
    assert set(identities.values()) == {2}
    assert len({p["patient_id"] for p in edge}) == 10


def test_birth_dates_precede_reference_date_and_cover_age_groups():
    profile, patients = generated()
    assert all(p["birth_date"] < profile["reference_date"] for p in patients)
    years = {int(p["birth_date"][:4]) for p in patients}
    assert any(year >= 2012 for year in years)
    assert any(year <= 1959 for year in years)
    assert any(1960 <= year <= 2005 for year in years)


def test_probe_contains_one_real_fixture_patient():
    profile, patients = generated()
    probe = select_probe(build_manifest(profile, patients))
    assert probe["probe"] is True
    assert len(probe["patients"]) == 1
    assert probe["patients"][0] == patients[0]


def test_full_confirmation_accepts_exact_count():
    profile, patients = generated()
    manifest = build_manifest(profile, patients)
    args = argparse.Namespace(environment=APPROVED_ENVIRONMENT, confirm_patient_count=100)
    validate_commit_confirmation(args, manifest)


@pytest.mark.parametrize(
    ("environment", "count"),
    [(None, 100), ("production", 100), (APPROVED_ENVIRONMENT, None), (APPROVED_ENVIRONMENT, 99)],
)
def test_commit_rejects_incorrect_confirmation(environment, count):
    profile, patients = generated()
    manifest = build_manifest(profile, patients)
    args = argparse.Namespace(environment=environment, confirm_patient_count=count)
    with pytest.raises(PatientDemographicsError):
        validate_commit_confirmation(args, manifest)


def test_profile_rejects_nonlocal_environment(tmp_path: Path):
    profile = load_profile()
    profile["environment"] = "production"
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(PatientDemographicsError):
        load_profile(path)


def test_receiver_uses_supported_service_and_transaction_guards():
    receiver = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "synthetic"
        / "openemr_patient_receiver.php"
    ).read_text(encoding="utf-8")
    assert "new PatientService()" in receiver
    assert "START TRANSACTION" in receiver
    assert "ROLLBACK" in receiver
    assert receiver.index("$verification = verifyPatients($payload)") < receiver.index("sqlStatement('COMMIT')")
    assert "Duplicate public patient identifier detected" in receiver
    assert "SYNTHETIC_POPULATION_V1" in receiver
    assert "$_GET['site'] = 'default';" in receiver


def test_receiver_template_avoids_large_command_line_payloads():
    runner = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "synthetic"
        / "patient_demographics.py"
    ).read_text(encoding="utf-8")
    assert "__SYNTH_PATIENT_PAYLOAD_BASE64__" in runner
    assert "input=rendered.encode" in runner
    assert "SYNTH_PATIENT_B64" not in runner
