from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIGRATION = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "interop-db"
    / "init"
    / "024-orm-accession-ownership.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(
        encoding="utf-8"
    ).lower()


def test_migration_defines_orm_ownership_trigger():
    sql = migration_sql()

    assert (
        "enforce_orm_accession_ownership"
        in sql
    )

    assert (
        "trg_enforce_orm_accession_ownership"
        in sql
    )

    assert (
        "before insert or update"
        in sql
    )


def test_exact_transaction_replay_remains_allowed():
    sql = migration_sql()

    assert "tg_op = 'insert'" in sql

    assert (
        "transaction_id = new.transaction_id"
        in sql
    )

    assert "return new" in sql


def test_accession_claims_are_serialized():
    sql = migration_sql()

    assert "pg_advisory_xact_lock" in sql
    assert "hashtext(new.accession_number)" in sql


def test_patient_order_and_procedure_define_ownership():
    sql = migration_sql()

    assert "existing.patient_identifier" in sql
    assert "existing.placer_order_number" in sql
    assert "existing.procedure_code" in sql
    assert "is distinct from" in sql


def test_conflicting_ownership_fails_closed():
    sql = migration_sql()

    assert "raise exception" in sql
    assert "orm accession ownership conflict" in sql
    assert "errcode = '23514'" in sql