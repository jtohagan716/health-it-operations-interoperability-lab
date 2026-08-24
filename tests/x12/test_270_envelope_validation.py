from pathlib import Path

from scripts.x12.eligibility_270 import (
    load_x12,
    validate_270_envelopes,
)

from scripts.x12.eligibility_270 import (
    load_x12,
    parse_270_business_data,
    validate_270_envelopes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-valid.edi"
)


def test_valid_270_preserves_envelope_control_numbers():
    segments = load_x12(VALID_270)

    result = validate_270_envelopes(segments)

    assert result["transaction_type"] == "270"
    assert result["isa_control_number"] == "000000101"
    assert result["gs_control_number"] == "101"
    assert result["st_control_number"] == "0001"

import pytest


INVALID_ST_CONTROL_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-invalid-st-control.edi"
)


def test_270_rejects_mismatched_st_se_control_numbers():
    segments = load_x12(INVALID_ST_CONTROL_270)

    with pytest.raises(
        ValueError,
        match="ST/SE transaction-set control numbers do not match",
    ):
        validate_270_envelopes(segments)

INVALID_ISA_IEA_CONTROL_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-invalid-isa-iea-control.edi"
)

INVALID_GS_GE_CONTROL_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-invalid-gs-ge-control.edi"
)


def test_270_rejects_mismatched_isa_iea_control_numbers():
    segments = load_x12(INVALID_ISA_IEA_CONTROL_270)

    with pytest.raises(
        ValueError,
        match="ISA/IEA interchange control numbers do not match",
    ):
        validate_270_envelopes(segments)


def test_270_rejects_mismatched_gs_ge_control_numbers():
    segments = load_x12(INVALID_GS_GE_CONTROL_270)

    with pytest.raises(
        ValueError,
        match="GS/GE functional-group control numbers do not match",
    ):
        validate_270_envelopes(segments)

import pytest


INVALID_ST_CONTROL_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-invalid-st-control.edi"
)

def test_270_rejects_mismatched_st_se_control_numbers():
    segments = load_x12(INVALID_ST_CONTROL_270)

    with pytest.raises(
        ValueError,
        match="ST/SE transaction-set control numbers do not match",
    ):
        validate_270_envelopes(segments)

def test_valid_270_preserves_eligibility_business_data():
    segments = load_x12(VALID_270)

    result = parse_270_business_data(segments)

    assert result["payer_name"] == "DEMO HEALTH PLAN"
    assert result["provider_name"] == "DEMO CLINIC"

    assert result["subscriber_first_name"] == "JOHN"
    assert result["subscriber_last_name"] == "DOE"

    assert result["member_id"] == "MEMBER1001"

    assert result["eligibility_date"] == "20260823"

    assert result["benefit_code"] == "30"

INVALID_MISSING_MEMBER_ID_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-invalid-missing-member-id.edi"
)

def test_270_rejects_missing_subscriber_member_id():
    segments = load_x12(INVALID_MISSING_MEMBER_ID_270)

    with pytest.raises(
        ValueError,
        match="missing the subscriber member ID",
    ):
        parse_270_business_data(segments)

INVALID_MISSING_ELIGIBILITY_DATE_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-invalid-missing-eligibility-date.edi"
)

def test_270_rejects_missing_eligibility_date():
    segments = load_x12(
        INVALID_MISSING_ELIGIBILITY_DATE_270
    )

    with pytest.raises(
        ValueError,
        match="missing the eligibility date",
    ):
        parse_270_business_data(segments)