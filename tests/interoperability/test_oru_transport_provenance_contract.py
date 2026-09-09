from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIGRATION_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "interop-db"
    / "init"
    / "022-oru-transport-provenance.sql"
)

CHANNEL_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "channels"
    / "ORU_R01_IN.xml"
)


def migration_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def channel_text() -> str:
    return CHANNEL_PATH.read_text(encoding="utf-8")


def test_migration_marks_only_existing_orus_as_legacy_unlinked():
    text = migration_text()

    assert "ADD COLUMN provenance_status VARCHAR(30)" in text
    assert "UPDATE audit.oru_messages" in text
    assert "SET provenance_status = 'LEGACY_UNLINKED'" in text
    assert "ALTER COLUMN provenance_status" in text
    assert "SET NOT NULL" in text
    assert "DEFAULT 'LEGACY_UNLINKED'" not in text


def test_migration_requires_complete_linked_provenance():
    text = migration_text()

    assert "ADD COLUMN transaction_id BIGINT" in text
    assert "ADD COLUMN source_audit_id BIGINT" in text
    assert "provenance_status = 'LINKED'" in text
    assert "transaction_id IS NOT NULL" in text
    assert "source_audit_id IS NOT NULL" in text


def test_migration_links_oru_to_logical_transaction():
    text = migration_text()

    assert "ADD CONSTRAINT fk_oru_messages_transaction" in text
    assert "FOREIGN KEY (transaction_id)" in text
    assert "REFERENCES audit.interface_transactions" in text


def test_migration_proves_source_attempt_belongs_to_transaction():
    text = migration_text()

    assert "uq_interface_messages_audit_transaction" in text
    assert "UNIQUE (\n        audit_id,\n        transaction_id\n    )" in text
    assert "ADD CONSTRAINT fk_oru_messages_source_receipt" in text
    assert "source_audit_id,\n            transaction_id" in text
    assert "audit_id,\n            transaction_id" in text


def test_migration_allows_one_semantic_oru_per_transaction():
    text = migration_text()

    assert "CREATE UNIQUE INDEX" in text
    assert "uq_oru_messages_transaction" in text
    assert "ON audit.oru_messages(transaction_id)" in text
    assert "WHERE transaction_id IS NOT NULL" in text


def test_oru_channel_records_every_transport_receipt():
    text = channel_text()

    assert "audit.record_interface_receipt" in text
    assert "oru_payload_sha256" in text
    assert "audit_recorded_audit_id" in text
    assert "audit_logical_transaction_id" in text
    assert "audit_attempt_outcome" in text


def test_oru_channel_recognizes_all_receipt_classifications():
    text = channel_text()

    assert "FIRST_DELIVERY" in text
    assert "EXACT_REPLAY" in text
    assert "CONFLICTING_REUSE" in text


def test_oru_channel_persists_enforced_provenance():
    text = channel_text()

    assert "transaction_id" in text
    assert "source_audit_id" in text
    assert "provenance_status" in text
    assert "LINKED" in text


def test_oru_ack_policy_rejects_conflicting_reuse():
    text = channel_text()

    assert 'classifiedOutcome == &quot;CONFLICTING_REUSE&quot;' in text
    assert 'ackCode = &quot;AR&quot;' in text

