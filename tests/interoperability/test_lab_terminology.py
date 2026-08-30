import pytest

from scripts.terminology.lab_terminology import (
    validate_lab_observation_terminology,
)


def test_accepts_supported_glucose_loinc_and_ucum():
    validate_lab_observation_terminology(
        code="2345-7",
        display="Glucose",
        coding_system="LN",
        unit="mg/dL",
    )


def test_rejects_wrong_display_for_loinc_code():
    with pytest.raises(
        ValueError,
        match="LOINC semantic mismatch",
    ):
        validate_lab_observation_terminology(
            code="2345-7",
            display="Potassium",
            coding_system="LN",
            unit="mg/dL",
        )


def test_rejects_wrong_coding_system():
    with pytest.raises(
        ValueError,
        match="Expected HL7 v2 coding system LN",
    ):
        validate_lab_observation_terminology(
            code="2345-7",
            display="Glucose",
            coding_system="SNOMED",
            unit="mg/dL",
        )


def test_rejects_incompatible_ucum_unit():
    with pytest.raises(
        ValueError,
        match="UCUM unit mismatch",
    ):
        validate_lab_observation_terminology(
            code="2345-7",
            display="Glucose",
            coding_system="LN",
            unit="mmHg",
        )