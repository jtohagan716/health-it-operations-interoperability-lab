from pathlib import Path

from scripts.x12.eligibility_271 import (
    parse_271_business_data,
    validate_271_envelopes,
)
from scripts.x12.eligibility_270 import load_x12


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_271 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "271-valid.edi"
)


def test_valid_271_preserves_envelope_control_numbers():
    segments = load_x12(VALID_271)

    result = validate_271_envelopes(segments)

    assert result["transaction_type"] == "271"
    assert result["isa_control_number"] == "000000201"
    assert result["gs_control_number"] == "201"
    assert result["st_control_number"] == "0002"


def test_valid_271_preserves_eligibility_response_data():
    segments = load_x12(VALID_271)

    result = parse_271_business_data(segments)

    assert result["payer_name"] == "DEMO HEALTH PLAN"
    assert result["provider_name"] == "DEMO CLINIC"

    assert result["subscriber_first_name"] == "JOHN"
    assert result["subscriber_last_name"] == "DOE"

    assert result["member_id"] == "MEMBER1001"

    assert result["trace_number"] == "ELIGREQ0001"

    assert result["eligibility_date"] == "20260823"

    assert result["eligibility_status"] == "1"
    assert result["benefit_code"] == "30"