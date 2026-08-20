from pathlib import Path

from scripts.hl7.analyze_adt import analyze_adt


GOOD_FIXTURE = Path(
    "fixtures/hl7/adt/adt-a04-lab000001.hl7"
)

INVALID_FIXTURE = Path(
    "fixtures/hl7/adt/adt-a04-invalid.hl7"
)

EVENT_MISMATCH_FIXTURE = Path(
    "fixtures/hl7/adt/adt-a04-event-mismatch.hl7"
)


def test_valid_adt_a04_passes_all_field_validations():
    result = analyze_adt(GOOD_FIXTURE)

    failed_checks = [
        description
        for description, passed in result["checks"].items()
        if not passed
    ]

    assert failed_checks == []


def test_invalid_adt_a04_reports_expected_failures():
    result = analyze_adt(INVALID_FIXTURE)

    checks = result["checks"]

    assert checks["Patient ID present"] is False
    assert checks["Assigning authority present"] is False
    assert checks["Identifier type is MR"] is False
    assert checks["Given name present"] is False
    assert checks["Patient class recognized"] is False
    assert checks["Visit number present"] is False
    assert checks["Message control ID present"] is False
    assert checks["Administrative sex recognized"] is False

    assert checks["Message type is ADT"] is True
    assert checks["Trigger event is A04"] is True
    assert checks["HL7 version is 2.5.1"] is True


def test_event_mismatch_is_detected():
    result = analyze_adt(EVENT_MISMATCH_FIXTURE)

    checks = result["checks"]

    assert checks["Message type is ADT"] is True
    assert checks["Trigger event is A04"] is True
    assert checks["EVN event type present"] is True

    assert (
        checks["EVN event type matches MSH trigger event"]
        is False
    )

def test_good_fixture_places_name_type_in_xpn_7():
    result = analyze_adt(GOOD_FIXTURE)

    pid_fields = result["pid"].split("|")
    patient_name = pid_fields[5]
    name_components = patient_name.split("^")

    assert len(name_components) >= 7, (
        "PID-5 must carry Name Type Code in XPN.7."
    )

    assert name_components[5] == ""
    assert name_components[6] == "L"
def test_analyzer_reads_name_type_from_xpn_7():
    result = analyze_adt(GOOD_FIXTURE)

    assert result["name_type"] == "L"

def test_valid_adt_a04_recognizes_patient_name_type():
    result = analyze_adt(GOOD_FIXTURE)

    assert result["checks"]["Patient name type recognized"] is True

def test_unrecognized_patient_name_type_is_detected(tmp_path):
    source = GOOD_FIXTURE.read_text(encoding="utf-8")

    valid_name = "Testpatient^Avery^^^^^L"
    invalid_name = "Testpatient^Avery^^^^^XYZ"

    assert valid_name in source

    malformed_message = source.replace(
        valid_name,
        invalid_name,
        1,
    )

    malformed_fixture = tmp_path / "adt-a04-invalid-name-type.hl7"
    malformed_fixture.write_text(
        malformed_message,
        encoding="utf-8",
    )

    result = analyze_adt(malformed_fixture)

    assert result["name_type"] == "XYZ"

    failed_checks = [
        description
        for description, passed in result["checks"].items()
        if not passed
    ]

    assert failed_checks == ["Patient name type recognized"]
