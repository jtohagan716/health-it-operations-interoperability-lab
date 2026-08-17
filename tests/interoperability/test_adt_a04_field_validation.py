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