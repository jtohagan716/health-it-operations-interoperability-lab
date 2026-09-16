from collections import Counter
import re
import pytest

from scripts.synthetic.clinical_history import (
    ClinicalHistoryError,
    build_allergies,
    build_clinical_history,
    build_immunizations,
    build_manifest,
    build_medications,
    cohort_for,
    load_population_profile,
    load_profile,
    patient_base_date,
    select_patient_probe,
)

from datetime import datetime


def profiles():
    return load_profile(), load_population_profile()


def test_profile_is_guarded_and_has_issue_31_targets():
    profile, _ = profiles()

    assert profile["issue"] == 31
    assert profile["environment"] == "local-lab"
    assert profile["synthetic_only"] is True
    assert profile["source_system"] == "SYNTHETIC_POPULATION_V1"
    assert profile["targets"] == {
        "medications": 200,
        "allergies": 100,
        "immunizations": 200,
    }


def test_cohort_assignment_matches_population_rotation():
    _, population = profiles()

    expected = population["cohorts"]

    assert [
        cohort_for(i, population)
        for i in range(1, 11)
    ] == expected

    assert Counter(
        cohort_for(i, population)
        for i in range(1, 101)
    ) == Counter(
        {
            cohort: 10
            for cohort in expected
        }
    )


@pytest.mark.parametrize("sequence", [0, 101])
def test_invalid_patient_sequence_fails_closed(sequence):
    _, population = profiles()

    with pytest.raises(ClinicalHistoryError):
        cohort_for(sequence, population)


def test_allergy_generation_is_deterministic_and_complete():
    profile, population = profiles()

    first = build_allergies(profile, population)
    second = build_allergies(profile, population)

    assert first == second
    assert len(first) == 100
    assert len(
        {
            record["external_id"]
            for record in first
        }
    ) == 100

    assert {
        record["mrn"]
        for record in first
    } == {
        f"SYNTHMRN{i:06d}"
        for i in range(1, 101)
    }


def test_every_patient_has_exactly_one_allergy():
    profile, population = profiles()
    records = build_allergies(profile, population)

    counts = Counter(
        record["mrn"]
        for record in records
    )

    assert len(counts) == 100
    assert set(counts.values()) == {1}


def test_immunization_generation_is_deterministic_and_complete():
    profile, population = profiles()

    first = build_immunizations(profile, population)
    second = build_immunizations(profile, population)

    assert first == second
    assert len(first) == 200
    assert len(
        {
            record["external_id"]
            for record in first
        }
    ) == 200


def test_every_patient_has_exactly_two_immunizations():
    profile, population = profiles()
    records = build_immunizations(profile, population)

    counts = Counter(
        record["mrn"]
        for record in records
    )

    assert len(counts) == 100
    assert set(counts.values()) == {2}


def test_generated_records_preserve_patient_cohort():
    profile, population = profiles()

    records = (
        build_allergies(profile, population)
        + build_immunizations(profile, population)
    )

    for record in records:
        sequence = int(record["mrn"][-6:])

        assert record["cohort"] == cohort_for(
            sequence,
            population,
        )


def test_medication_generation_is_deterministic_and_hits_target():
    profile, population = profiles()

    first = build_medications(profile, population)
    second = build_medications(profile, population)

    assert first == second
    assert len(first) == 200
    assert len(
        {
            record["external_id"]
            for record in first
        }
    ) == 200


def test_medication_distribution_matches_cohort_contract():
    profile, population = profiles()
    records = build_medications(profile, population)

    counts = Counter(
        record["cohort"]
        for record in records
    )

    assert counts == Counter(
        {
            "PREVENTIVE": 10,
            "HYPERTENSION": 30,
            "PREDIABETES": 10,
            "DIABETES": 30,
            "RESPIRATORY": 30,
            "CARDIOVASCULAR": 30,
            "PEDIATRIC": 10,
            "OLDER_ADULT": 30,
            "RESULT_LIFECYCLE": 10,
            "IDENTITY_EDGE": 10,
        }
    )


def test_disease_specific_cohorts_include_expected_medication():
    profile, population = profiles()
    records = build_medications(profile, population)

    by_patient: dict[str, list[dict]] = {}

    for record in records:
        by_patient.setdefault(
            record["mrn"],
            [],
        ).append(record)

    expectations = {
        "HYPERTENSION": "lisinopril",
        "DIABETES": "metformin",
        "RESPIRATORY": "albuterol",
        "CARDIOVASCULAR": "atorvastatin",
    }

    for medications in by_patient.values():
        cohort = medications[0]["cohort"]

        if cohort not in expectations:
            continue

        expected = expectations[cohort]

        assert any(
            expected.lower()
            in medication["drug"].lower()
            for medication in medications
        )


def test_all_generated_clinical_history_ids_are_globally_unique():
    profile, population = profiles()

    history = build_clinical_history(
        profile,
        population,
    )

    records = (
        history["medications"]
        + history["allergies"]
        + history["immunizations"]
    )

    ids = [
        record["external_id"]
        for record in records
    ]

    assert len(records) == 500
    assert len(ids) == len(set(ids))


def test_complete_clinical_history_hits_issue_31_targets():
    profile, population = profiles()

    history = build_clinical_history(
        profile,
        population,
    )

    assert {
        domain: len(records)
        for domain, records in history.items()
    } == {
        "medications": 200,
        "allergies": 100,
        "immunizations": 200,
    }

def test_generated_clinical_dates_are_deterministic():
    profile, population = profiles()

    first = build_clinical_history(profile, population)
    second = build_clinical_history(profile, population)

    assert first == second

    assert first["medications"][0]["start_date"] == "2024-07-19"
    assert first["allergies"][0]["begdate"] == "2024-01-16"
    assert (
        first["immunizations"][0]["administered_date"]
        == "2024-05-20"
    )
    assert (
        first["immunizations"][1]["administered_date"]
        == "2024-09-17"
    )

def test_clinical_history_precedes_patient_base_date():
    profile, population = profiles()
    history = build_clinical_history(profile, population)

    for domain, date_field in (
        ("medications", "start_date"),
        ("allergies", "begdate"),
        ("immunizations", "administered_date"),
    ):
        for record in history[domain]:
            sequence = int(record["mrn"][-6:])
            base = patient_base_date(profile, sequence)
            clinical_date = datetime.strptime(
                record[date_field],
                "%Y-%m-%d",
            )

            assert clinical_date < base

def test_manifest_has_expected_population_counts():
    profile, population = profiles()

    manifest = build_manifest(profile, population)

    assert manifest["expected_counts"] == {
        "medications": 200,
        "allergies": 100,
        "immunizations": 200,
    }

    assert len(manifest["records"]) == 500


def test_manifest_records_have_required_schema_identity():
    profile, population = profiles()

    manifest = build_manifest(profile, population)

    for record in manifest["records"]:
        assert record["entity_type"] in {
            "medication",
            "allergy",
            "immunization",
        }
        assert record["logical_key"] == record["external_id"]
        assert (
            record["source_system"]
            == "SYNTHETIC_POPULATION_V1"
        )


def test_manifest_logical_keys_are_globally_unique():
    profile, population = profiles()

    manifest = build_manifest(profile, population)

    logical_keys = [
        record["logical_key"]
        for record in manifest["records"]
    ]

    assert len(logical_keys) == 500
    assert len(logical_keys) == len(set(logical_keys))


def test_dry_run_manifest_has_zero_execution_outcomes():
    profile, population = profiles()

    manifest = build_manifest(profile, population)

    assert manifest["outcomes"] == {
        "medications": {
            "expected": 200,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "reconciled": 0,
        },
        "allergies": {
            "expected": 100,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "reconciled": 0,
        },
        "immunizations": {
            "expected": 200,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "reconciled": 0,
        },
    }

def test_generated_manifest_conforms_to_repository_contract():
    profile, population = profiles()
    manifest = build_manifest(profile, population)

    required = {
        "run_id",
        "profile_version",
        "seed",
        "environment",
        "synthetic_only",
        "generated_at",
        "source_system",
        "expected_counts",
        "outcomes",
    }

    assert required.issubset(manifest)

    assert re.fullmatch(
        r"SYNTH-[0-9]{8}-[0-9]{3,}",
        manifest["run_id"],
    )

    assert re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+",
        manifest["profile_version"],
    )

    assert manifest["seed"] >= 1
    assert manifest["environment"] == "local-lab"
    assert manifest["synthetic_only"] is True
    assert (
        manifest["source_system"]
        == "SYNTHETIC_POPULATION_V1"
    )

    generated_at = datetime.fromisoformat(
        manifest["generated_at"]
    )
    assert generated_at.tzinfo is not None

    assert manifest["expected_counts"] == {
        "medications": 200,
        "allergies": 100,
        "immunizations": 200,
    }

    for outcome in manifest["outcomes"].values():
        assert set(outcome) == {
            "expected",
            "attempted",
            "succeeded",
            "failed",
            "reconciled",
        }

        assert all(
            isinstance(value, int) and value >= 0
            for value in outcome.values()
        )

    assert len(manifest["records"]) == 500

    for record in manifest["records"]:
        assert record["entity_type"]
        assert record["logical_key"]
        assert (
            record["source_system"]
            == "SYNTHETIC_POPULATION_V1"
        )

def test_patient_probe_selects_only_requested_patient():
    profile, population = profiles()

    manifest = build_manifest(profile, population)
    probe = select_patient_probe(
        manifest,
        "SYNTHMRN000002",
    )

    assert len(probe["records"]) == 6

    assert {
        record["mrn"]
        for record in probe["records"]
    } == {"SYNTHMRN000002"}

    assert probe["expected_counts"] == {
        "medications": 3,
        "allergies": 1,
        "immunizations": 2,
    }


def test_patient_probe_preserves_expected_logical_keys():
    profile, population = profiles()

    manifest = build_manifest(profile, population)
    probe = select_patient_probe(
        manifest,
        "SYNTHMRN000002",
    )

    assert {
        record["logical_key"]
        for record in probe["records"]
    } == {
        "SYNMED00000201",
        "SYNMED00000202",
        "SYNMED00000203",
        "SYNALG00000201",
        "SYNIMM00000201",
        "SYNIMM00000202",
    }


def test_patient_probe_rejects_invalid_or_unknown_patient():
    profile, population = profiles()
    manifest = build_manifest(profile, population)

    with pytest.raises(
        ClinicalHistoryError,
        match="SYNTHMRN identifier namespace",
    ):
        select_patient_probe(
            manifest,
            "REALPATIENT000002",
        )

    with pytest.raises(
        ClinicalHistoryError,
        match="No clinical-history records found",
    ):
        select_patient_probe(
            manifest,
            "SYNTHMRN999999",
        )