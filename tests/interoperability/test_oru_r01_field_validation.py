from pathlib import Path

from scripts.hl7.analyze_oru import analyze_oru


GOOD_FIXTURE = Path(
    "fixtures/hl7/oru/oru-r01-lab000001.hl7"
)


def test_valid_oru_r01_passes_all_field_validations():
    result = analyze_oru(GOOD_FIXTURE)

    failed_checks = [
        description
        for description, passed in result["checks"].items()
        if not passed
    ]

    assert failed_checks == []


def test_numeric_obx_rejects_non_numeric_result(tmp_path):
    source = GOOD_FIXTURE.read_text(encoding="utf-8")

    modified = source.replace(
        "||105|mg/dL|",
        "||ABC|mg/dL|",
        1,
    )

    fixture = tmp_path / "oru-r01-invalid-numeric.hl7"
    fixture.write_text(modified, encoding="utf-8")

    result = analyze_oru(fixture)

    assert (
        result["checks"]["Numeric OBX contains numeric value"]
        is False
    )


def test_obr_obx_code_mismatch_is_detected(tmp_path):
    source = GOOD_FIXTURE.read_text(encoding="utf-8")

    modified = source.replace(
        "OBX|1|NM|2345-7^Glucose^LN",
        "OBX|1|NM|2823-3^Potassium^LN",
        1,
    )

    fixture = tmp_path / "oru-r01-code-mismatch.hl7"
    fixture.write_text(modified, encoding="utf-8")

    result = analyze_oru(fixture)

    assert (
        result["checks"]["OBR and OBX observation codes agree"]
        is False
    )


def test_unrecognized_abnormal_flag_is_detected(tmp_path):
    source = GOOD_FIXTURE.read_text(encoding="utf-8")

    modified = source.replace(
        "|70-99|H|||F",
        "|70-99|XYZ|||F",
        1,
    )

    fixture = tmp_path / "oru-r01-invalid-abnormal-flag.hl7"
    fixture.write_text(modified, encoding="utf-8")

    result = analyze_oru(fixture)

    assert (
        result["checks"]["OBX abnormal flag recognized"]
        is False
    )


def test_obr_obx_result_status_mismatch_is_detected(tmp_path):
    source = GOOD_FIXTURE.read_text(encoding="utf-8")

    modified = source.replace(
        "|70-99|H|||F",
        "|70-99|H|||P",
        1,
    )

    fixture = tmp_path / "oru-r01-status-mismatch.hl7"
    fixture.write_text(modified, encoding="utf-8")

    result = analyze_oru(fixture)

    assert (
        result["checks"]["OBR and OBX result status agree"]
        is False
    )