import argparse
from collections import Counter
from pathlib import Path

import pytest

from scripts.synthetic.encounter_vitals import (
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
        / "openemr_encounter_vitals_receiver.php"
    ).read_text(encoding="utf-8")


def test_profile_is_restricted_to_synthetic_local_lab():
    value = profile()
    assert value["synthetic_only"] is True
    assert value["environment"] == "local-lab"
    assert value["issue"] == 31
    assert value["patient_count"] == 100
    assert value["encounters_per_patient"] == 3


def test_full_population_has_three_records_per_patient():
    records = build_records(profile())
    counts = Counter(row["mrn"] for row in records)

    assert len(records) == 300
    assert len(counts) == 100
    assert set(counts.values()) == {3}


def test_identifiers_are_stable_unique_and_within_column_limit():
    records = build_records(profile())
    encounter_ids = [row["encounter_external_id"] for row in records]
    vitals_ids = [row["vitals_external_id"] for row in records]

    assert records[0]["mrn"] == "SYNTHMRN000001"
    assert records[-1]["mrn"] == "SYNTHMRN000100"
    assert encounter_ids[0] == "SYNENC00000101"
    assert encounter_ids[-1] == "SYNENC00010003"
    assert vitals_ids[0] == "SYNVIT00000101"
    assert vitals_ids[-1] == "SYNVIT00010003"
    assert len(set(encounter_ids)) == 300
    assert len(set(vitals_ids)) == 300
    assert all(len(value) <= 20 for value in encounter_ids)
    assert all(len(value) <= 20 for value in vitals_ids)


def test_first_visit_preserves_original_identifiers_and_timestamp():
    first = build_records(profile())[0]

    assert first == {
        "mrn": "SYNTHMRN000001",
        "visit_sequence": 1,
        "encounter_external_id": "SYNENC00000101",
        "vitals_external_id": "SYNVIT00000101",
        "encounter_at": "2025-01-15 10:00:00",
        "vitals_at": "2025-01-15 10:15:00",
    }


def test_probe_contains_all_three_visits_for_first_golden_patient():
    records = build_records(profile(), probe=True)

    assert len(records) == 3
    assert {row["mrn"] for row in records} == {"SYNTHMRN000001"}
    assert [row["visit_sequence"] for row in records] == [1, 2, 3]
    assert [row["encounter_external_id"] for row in records] == [
        "SYNENC00000101",
        "SYNENC00000102",
        "SYNENC00000103",
    ]


def test_dates_are_deterministic_chronological_and_historical():
    records = build_records(profile(), probe=True)
    again = build_records(profile(), probe=True)

    assert records == again
    assert [row["encounter_at"] for row in records] == [
        "2025-01-15 10:00:00",
        "2025-05-15 10:00:00",
        "2025-09-12 10:00:00",
    ]
    assert all(
        row["vitals_at"] > row["encounter_at"]
        for row in records
    )


def test_visit_schedule_matches_declared_encounter_count():
    value = profile()
    schedule = value["visit_schedule"]

    assert len(schedule) == value["encounters_per_patient"]
    assert [visit["sequence"] for visit in schedule] == [1, 2, 3]
    assert [visit["offset_days"] for visit in schedule] == [0, 120, 240]
    assert schedule[0]["reason_suffix"] == ""
    assert schedule[0]["vital_adjustments"] == {}


def test_all_population_cohorts_have_templates():
    expected = {
        "PREVENTIVE",
        "PREDIABETES",
        "DIABETES",
        "HYPERTENSION",
        "CARDIOVASCULAR",
        "RESPIRATORY",
        "PEDIATRIC",
        "OLDER_ADULT",
        "IDENTITY_EDGE",
        "RESULT_LIFECYCLE",
    }
    assert set(profile()["cohort_defaults"]) == expected


@pytest.mark.parametrize(
    "cohort",
    [
        "PREVENTIVE",
        "DIABETES",
        "HYPERTENSION",
        "RESPIRATORY",
        "PEDIATRIC",
        "OLDER_ADULT",
    ],
)
def test_vital_templates_are_numeric_and_positive(cohort):
    vital = profile()["cohort_defaults"][cohort]

    for field in (
        "bps",
        "bpd",
        "weight",
        "height",
        "temperature",
        "pulse",
        "respiration",
        "oxygen_saturation",
    ):
        assert isinstance(vital[field], (int, float))
        assert vital[field] > 0


def test_visit_adjustments_only_target_supported_numeric_vitals():
    value = profile()
    supported = {
        "bps",
        "bpd",
        "weight",
        "height",
        "temperature",
        "pulse",
        "respiration",
        "oxygen_saturation",
    }

    for visit in value["visit_schedule"]:
        adjustments = visit["vital_adjustments"]
        assert set(adjustments).issubset(supported)
        assert all(
            isinstance(adjustment, (int, float))
            for adjustment in adjustments.values()
        )


def test_payload_separates_patient_and_record_counts():
    full = build_payload(profile(), verify_only=True)
    probe = build_payload(profile(), probe=True, verify_only=True)

    assert full["verify_only"] is True
    assert full["expected_patients"] == 100
    assert full["expected_records"] == 300
    assert len(full["records"]) == 300

    assert probe["expected_patients"] == 1
    assert probe["expected_records"] == 3
    assert len(probe["records"]) == 3


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


def test_receiver_uses_native_services_and_recovery_guards():
    source = receiver_source()

    for expected in (
        "insertEncounter",
        "insertVital",
        "FormVitals",
        "sqlBeginTrans",
        "sqlCommitTrans",
        "sqlRollbackTrans",
        "compensating_cleanup",
    ):
        assert expected in source


def test_receiver_verifies_both_form_registrations():
    source = receiver_source()

    assert "formdir='newpatient'" in source
    assert "formdir='vitals'" in source


def test_receiver_establishes_background_execution_identity():
    source = receiver_source()

    assert "authUserID" in source
    assert "SessionWrapperFactory" in source


def test_vitals_correlation_does_not_depend_on_filtered_external_id():
    source = receiver_source()

    assert (
        "Deterministic synthetic historical vitals ' . "
        "$record['vitals_external_id']"
    ) in source
    assert "FROM forms f JOIN form_vitals v" in source


def test_native_form_registration_id_is_diagnostic_not_authoritative():
    source = receiver_source()

    assert "native_vitals_form_id" in source
    assert "(int)$vitals['form_registration_id'] !==" not in source
    assert "DELETE FROM forms WHERE id=? AND formdir='vitals'" not in source
    assert (
        "DELETE FROM forms WHERE formdir='vitals' AND form_id=? "
        "AND pid=? AND encounter=?"
    ) in source


def test_receiver_tracks_every_encounter_without_mrn_key_collisions():
    source = receiver_source()

    assert "$outcomes[$record['encounter_external_id']]" in source
    assert "$verification[$record['encounter_external_id']]" in source
    assert "$outcomes[$record['mrn']]" not in source
    assert "$verification[$record['mrn']]" not in source
    assert "'record_outcomes' => $outcomes" in source


def test_receiver_verifies_dates_and_payload_cardinality():
    source = receiver_source()

    assert "$encounter['date'] !== $record['encounter_at']" in source
    assert "$vitals['date'] !== $record['vitals_at']" in source
    assert "Payload record count or identity mismatch" in source
    assert "Payload patient count mismatch" in source
    assert "'expected_records' => $expectedRecords" in source
    assert "'resolved_records' => count($verification)" in source
