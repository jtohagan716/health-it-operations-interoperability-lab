from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hl7"
    / "inspect_oru_results.ps1"
)


def load_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8-sig")


def test_inspection_script_is_present():
    assert SCRIPT_PATH.is_file()


def test_inspection_script_is_read_only():
    script = load_script().upper()

    prohibited_statements = (
        "INSERT INTO",
        "UPDATE AUDIT.",
        "DELETE FROM",
        "TRUNCATE ",
        "DROP TABLE",
        "ALTER TABLE",
    )

    for statement in prohibited_statements:
        assert statement not in script


def test_inspection_script_reconciles_required_tables():
    script = load_script()

    assert "audit.oru_messages" in script
    assert "audit.oru_observations" in script
    assert "o.oru_message_id = m.oru_message_id" in script


def test_inspection_script_exposes_clinical_semantics():
    script = load_script()

    required_fields = (
        "patient_identifier",
        "placer_order_number",
        "filler_order_number",
        "service_code",
        "observation_code",
        "observation_value",
        "units",
        "reference_range",
        "abnormal_flag",
        "result_status",
        "processing_status",
    )

    for field in required_fields:
        assert field in script


def test_inspection_script_uses_numeric_aggregation():
    script = load_script()

    assert "o.observation_value::numeric" in script
    assert "minimum_numeric_value" in script
    assert "maximum_numeric_value" in script


def test_inspection_script_does_not_store_password():
    script = load_script().lower()

    assert "password=" not in script
    assert "pgpassword" not in script
    assert "interop_app" in script
