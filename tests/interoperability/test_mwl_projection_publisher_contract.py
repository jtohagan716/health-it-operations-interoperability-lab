from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PUBLISHER_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "radiology"
    / "mwl_projection.py"
)


def publisher_source() -> str:
    return PUBLISHER_PATH.read_text(
        encoding="utf-8"
    )


def normalized_source() -> str:
    return " ".join(
        publisher_source().split()
    ).lower()


def test_publisher_uses_deterministic_dicom_uid():
    source = publisher_source()

    assert "uuid.uuid5" in source
    assert '"2.25."' in source
    assert "mwl_item_id" in source
    assert "accession_number" in source


def test_projection_claim_is_concurrency_safe():
    source = normalized_source()

    assert "for update skip locked" in source
    assert "'pending'" in source
    assert "'failed'" in source
    assert "'in_progress'" in source
    assert "claimed_at" in source

    assert (
        "projection_attempt_count + 1"
        in source
    )

    assert "stale" in source


def test_publisher_builds_required_worklist_identity():
    source = publisher_source()

    for field in (
        "PatientID",
        "PatientName",
        "PatientBirthDate",
        "PatientSex",
        "AccessionNumber",
        "StudyInstanceUID",
        "RequestedProcedureID",
        "RequestedProcedureDescription",
        "ScheduledProcedureStepSequence",
        "ScheduledStationAETitle",
        "ScheduledProcedureStepStartDate",
        "ScheduledProcedureStepStartTime",
        "Modality",
        "ScheduledProcedureStepID",
        "ScheduledProcedureStepDescription",
    ):
        assert f'"{field}"' in source


def test_retry_reconciles_before_create():
    source = publisher_source()

    assert '"/worklists/?format=Full"' in source
    assert "find_existing_worklist" in source

    reconciliation = source.index(
        "find_existing_worklist"
    )

    creation = source.index(
        '"/worklists/create"'
    )

    assert reconciliation < creation


def test_reconciliation_fails_closed_on_ambiguity():
    source = publisher_source()

    assert (
        "Multiple Orthanc worklists match"
        in source
    )

    assert (
        "Orthanc worklist identity mismatch"
        in source
    )


def test_success_records_complete_publication_identity():
    source = normalized_source()

    assert (
        "projection_status = 'published'"
        in source
    )

    assert "study_instance_uid" in source
    assert "orthanc_worklist_id" in source
    assert "published_at = current_timestamp" in source


def test_failure_remains_retryable_and_preserves_error():
    source = normalized_source()

    assert (
        "projection_status = 'failed'"
        in source
    )

    assert "last_error" in source
    assert "updated_at = current_timestamp" in source


def test_targeted_publication_requires_confirmation():
    source = publisher_source()

    assert "--mwl-item-id" in source
    assert "--confirm-mwl-item-id" in source

    assert (
        "confirmation does not match"
        in source
    )