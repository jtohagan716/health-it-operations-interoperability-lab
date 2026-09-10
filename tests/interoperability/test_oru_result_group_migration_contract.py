from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "interop-db"
    / "init"
    / "023-oru-result-groups.sql"
)


def migration_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_creates_ordered_result_group_parent():
    text = migration_text()

    assert "CREATE TABLE audit.oru_result_groups" in text
    assert "result_group_sequence INTEGER NOT NULL" in text
    assert "CHECK (result_group_sequence >= 1)" in text
    assert "UNIQUE (oru_message_id, result_group_sequence)" in text


def test_result_group_preserves_obr_semantics():
    text = migration_text()

    for column in (
        "obr_set_id",
        "placer_order_number",
        "filler_order_number",
        "service_code",
        "service_text",
        "service_coding_system",
        "observation_at",
        "result_status",
    ):
        assert column in text


def test_existing_messages_receive_one_truthful_backfilled_group():
    text = migration_text()

    assert "INSERT INTO audit.oru_result_groups" in text
    assert "m.oru_message_id" in text
    assert "m.received_at" in text
    assert "m.obr_result_status" in text
    assert "obr_set_id" in text
    assert "NULL" in text


def test_existing_observations_receive_deterministic_sequence():
    text = migration_text()

    assert "row_number() OVER" in text
    assert "PARTITION BY o.oru_message_id" in text
    assert "ORDER BY o.oru_observation_id" in text
    assert "observation_sequence = ranked.observation_sequence" in text


def test_observations_require_group_ownership_and_sequence():
    text = migration_text()

    assert "ALTER COLUMN oru_result_group_id SET NOT NULL" in text
    assert "ALTER COLUMN observation_sequence SET NOT NULL" in text
    assert "CHECK (observation_sequence >= 1)" in text
    assert "UNIQUE (" in text
    assert "oru_result_group_id," in text
    assert "observation_sequence" in text


def test_composite_foreign_key_prevents_cross_message_parenting():
    text = migration_text()

    assert "fk_oru_observations_result_group" in text
    assert "oru_result_group_id,\n            oru_message_id" in text
    assert "REFERENCES audit.oru_result_groups" in text


def test_historical_obx_set_ids_are_not_invented():
    text = migration_text()

    assert "ADD COLUMN obx_set_id VARCHAR(20)" in text
    assert "historical values are not inferred" in text
    assert "SET\n    obx_set_id" not in text


def test_migration_is_transactional():
    text = migration_text().strip()

    assert text.startswith("BEGIN;")
    assert text.endswith("COMMIT;")
