from pathlib import Path

import pytest

from scripts.x12.eligibility_270 import (
    load_x12,
    parse_270_business_data,
)
from scripts.x12.eligibility_271 import (
    parse_271_business_data,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_270 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "270-valid.edi"
)

VALID_271 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "271-valid.edi"
)

INVALID_WRONG_MEMBER_271 = (
    PROJECT_ROOT
    / "fixtures"
    / "x12"
    / "eligibility"
    / "271-invalid-wrong-member.edi"
)


def correlate_270_271(
    request: dict[str, str],
    response: dict[str, str],
) -> None:
    """
    Validate that a 271 Eligibility Response belongs to the
    corresponding 270 Eligibility Inquiry.

    A response can be structurally valid on its own but still
    be incorrect for a particular request. This function checks
    the business identifiers that should remain consistent
    across the request/response pair.
    """

    if response["member_id"] != request["member_id"]:
        raise ValueError(
            "271 response member ID does not match "
            "the 270 request member ID."
        )

    if response["trace_number"] != request["trace_number"]:
        raise ValueError(
            "271 response trace number does not match "
            "the 270 request trace number."
        )

    if response["payer_name"] != request["payer_name"]:
        raise ValueError(
            "271 response payer does not match "
            "the 270 request payer."
        )

    if response["provider_name"] != request["provider_name"]:
        raise ValueError(
            "271 response provider does not match "
            "the 270 request provider."
        )

    if (
        response["eligibility_date"]
        != request["eligibility_date"]
    ):
        raise ValueError(
            "271 response eligibility date does not match "
            "the 270 request eligibility date."
        )

    if response["benefit_code"] != request["benefit_code"]:
        raise ValueError(
            "271 response benefit code does not match "
            "the 270 request benefit code."
        )


def test_271_response_correlates_to_270_request():
    request_segments = load_x12(
        VALID_270
    )

    response_segments = load_x12(
        VALID_271
    )

    request = parse_270_business_data(
        request_segments
    )

    response = parse_271_business_data(
        response_segments
    )

    correlate_270_271(
        request,
        response,
    )


def test_271_wrong_member_is_rejected_for_270_request():
    request_segments = load_x12(
        VALID_270
    )

    response_segments = load_x12(
        INVALID_WRONG_MEMBER_271
    )

    request = parse_270_business_data(
        request_segments
    )

    response = parse_271_business_data(
        response_segments
    )

    with pytest.raises(
        ValueError,
        match="271 response member ID does not match",
    ):
        correlate_270_271(
            request,
            response,
        )