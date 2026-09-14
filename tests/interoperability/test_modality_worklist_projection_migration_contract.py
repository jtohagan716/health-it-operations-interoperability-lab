from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIGRATION_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "interop-db"
    / "init"
    / "025-modality-worklist-projection.sql"
)


def migration_sql() -> str:
    return MIGRATION_PATH.read_text(
        encoding="utf-8"
    ).lower()


def test_migration_is_transactional():
    sql = migration_sql().strip()

    assert sql.startswith("begin;")
    assert sql.endswith("commit;")


def test_migration_defines_one_projection_per_orm_order():
    sql = migration_sql()

    assert (
        "audit.modality_worklist_items"
        in sql
    )

    assert (
        "orm_order_id bigint not null unique"
        in sql
    )

    assert (
        "references audit.orm_orders"
        in sql
    )

    assert "on delete cascade" in sql


def test_migration_preserves_required_mwl_identity():
    sql = migration_sql()

    for field in (
        "patient_identifier",
        "patient_family_name",
        "patient_given_name",
        "patient_date_of_birth",
        "patient_administrative_sex",
        "accession_number",
        "requested_procedure_id",
        "procedure_code",
        "procedure_description",
        "modality",
        "scheduled_station_ae_title",
        "scheduled_start_date",
        "scheduled_start_time",
        "schedule_source",
        "scheduled_procedure_step_id",
    ):
        assert field in sql


def test_migration_constrains_dicom_values():
    sql = migration_sql()

    for constraint in (
        "ck_mwl_patient_dob",
        "ck_mwl_patient_sex",
        "ck_mwl_scheduled_date",
        "ck_mwl_scheduled_time",
        "ck_mwl_station_ae_length",
        "ck_mwl_step_id_length",
        "ck_mwl_schedule_source",
    ):
        assert constraint in sql

    assert "'order_datetime'" in sql
    assert "'explicit_schedule'" in sql


def test_projection_lifecycle_fails_closed():
    sql = migration_sql()

    assert "ck_mwl_projection_status" in sql
    assert "'pending'" in sql
    assert "'published'" in sql
    assert "'failed'" in sql
    assert "'cancelled'" in sql
    assert "ck_mwl_attempt_count" in sql
    assert "projection_attempt_count >= 0" in sql

    assert "ck_mwl_published_identity" in sql
    assert "study_instance_uid is not null" in sql
    assert "orthanc_worklist_id is not null" in sql


def test_parent_orm_identity_is_locked_and_enforced():
    sql = migration_sql()

    assert "enforce_mwl_orm_identity" in sql
    assert "trg_enforce_mwl_orm_identity" in sql
    assert "for share" in sql

    assert "new.patient_identifier" in sql
    assert "new.accession_number" in sql
    assert "new.requested_procedure_id" in sql
    assert "new.procedure_code" in sql

    assert "parent_order.patient_identifier" in sql
    assert "parent_order.accession_number" in sql
    assert "parent_order.placer_order_number" in sql
    assert "parent_order.procedure_code" in sql

    assert "is distinct from" in sql


def test_missing_or_conflicting_parent_fails_closed():
    sql = migration_sql()

    assert "raise exception" in sql
    assert "errcode = '23503'" in sql
    assert "errcode = '23514'" in sql

    assert (
        "mwl projection references missing"
        in sql
    )

    assert (
        "mwl projection identity does not match"
        in sql
    )


def test_projection_supports_retry_and_reconciliation():
    sql = migration_sql()

    assert "orthanc_worklist_id" in sql
    assert "projection_attempt_count" in sql
    assert "last_error" in sql
    assert "created_at" in sql
    assert "updated_at" in sql

    assert "idx_mwl_projection_status" in sql
    assert "idx_mwl_patient_identifier" in sql


def test_projection_lifecycle_supports_claim_and_completion():
    sql = migration_sql()

    assert "'in_progress'" in sql
    assert "claimed_at timestamptz" in sql
    assert "published_at timestamptz" in sql

    assert "ck_mwl_claimed_identity" in sql
    assert "claimed_at is not null" in sql

    assert "ck_mwl_published_identity" in sql
    assert "published_at is not null" in sql