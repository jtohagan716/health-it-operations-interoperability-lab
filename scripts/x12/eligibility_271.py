from scripts.x12.eligibility_270 import (
    find_segment,
    find_segments,
    validate_transaction_segment_count,
)


def validate_271_envelopes(
    segments: list[list[str]],
) -> dict[str, str]:
    """
    Validate envelope and control-number integrity for a
    271 Eligibility Response.
    """

    isa = find_segment(segments, "ISA")
    iea = find_segment(segments, "IEA")

    gs = find_segment(segments, "GS")
    ge = find_segment(segments, "GE")

    st = find_segment(segments, "ST")
    se = find_segment(segments, "SE")

    # ST01 identifies the transaction set.
    # 271 means Eligibility, Coverage or Benefit Information Response.
    if st[1] != "271":
        raise ValueError(
            f"Expected transaction type 271 but found {st[1]!r}."
        )

    # Interchange Control Header / Trailer control number.
    isa_control = isa[13]
    iea_control = iea[2]

    if isa_control != iea_control:
        raise ValueError(
            "ISA/IEA interchange control numbers do not match: "
            f"{isa_control!r} != {iea_control!r}"
        )

    # Functional Group Header / Trailer control number.
    gs_control = gs[6]
    ge_control = ge[2]

    if gs_control != ge_control:
        raise ValueError(
            "GS/GE functional-group control numbers do not match: "
            f"{gs_control!r} != {ge_control!r}"
        )

    # Transaction Set Header / Trailer control number.
    st_control = st[2]
    se_control = se[2]

    if st_control != se_control:
        raise ValueError(
            "ST/SE transaction-set control numbers do not match: "
            f"{st_control!r} != {se_control!r}"
        )

    validate_transaction_segment_count(segments)

    return {
        "transaction_type": st[1],
        "isa_control_number": isa_control,
        "gs_control_number": gs_control,
        "st_control_number": st_control,
    }


def parse_271_business_data(
    segments: list[list[str]],
) -> dict[str, str]:
    """
    Extract selected business information from the controlled
    synthetic 271 Eligibility Response used by this lab.
    """

    nm1_segments = find_segments(
        segments,
        "NM1",
    )

    # PR = payer.
    payer = next(
        (
            segment
            for segment in nm1_segments
            if len(segment) > 1
            and segment[1] == "PR"
        ),
        None,
    )

    # 1P = provider.
    provider = next(
        (
            segment
            for segment in nm1_segments
            if len(segment) > 1
            and segment[1] == "1P"
        ),
        None,
    )

    # IL = insured/subscriber.
    subscriber = next(
        (
            segment
            for segment in nm1_segments
            if len(segment) > 1
            and segment[1] == "IL"
        ),
        None,
    )

    if payer is None:
        raise ValueError(
            "271 eligibility response is missing the payer."
        )

    if provider is None:
        raise ValueError(
            "271 eligibility response is missing the provider."
        )

    if subscriber is None:
        raise ValueError(
            "271 eligibility response is missing the subscriber."
        )

    member_id = (
        subscriber[9]
        if len(subscriber) > 9
        else ""
    )

    if not member_id:
        raise ValueError(
            "271 eligibility response is missing the "
            "subscriber member ID."
        )

    # TRN = Trace segment.
    # In our controlled response, TRN02 carries the trace number
    # tying the response back to the original eligibility inquiry.
    trace = find_segment(
        segments,
        "TRN",
    )

    trace_number = (
        trace[2]
        if len(trace) > 2
        else ""
    )

    if not trace_number:
        raise ValueError(
            "271 eligibility response is missing the trace number."
        )

    # DTP = Date or Time Period.
    date_segments = find_segments(
        segments,
        "DTP",
    )

    eligibility_date_segment = next(
        (
            segment
            for segment in date_segments
            if len(segment) > 3
            and segment[1] == "291"
        ),
        None,
    )

    if eligibility_date_segment is None:
        raise ValueError(
            "271 eligibility response is missing the "
            "eligibility date."
        )

    # EB = Eligibility or Benefit Information.
    # This is the key response segment telling the provider
    # what the payer determined about coverage/benefits.
    eb = find_segment(
        segments,
        "EB",
    )

    eligibility_status = (
        eb[1]
        if len(eb) > 1
        else ""
    )

    benefit_code = (
        eb[3]
        if len(eb) > 3
        else ""
    )

    if not eligibility_status:
        raise ValueError(
            "271 eligibility response is missing the "
            "eligibility status."
        )

    if not benefit_code:
        raise ValueError(
            "271 eligibility response is missing the "
            "benefit code."
        )

    return {
        "payer_name": payer[3],
        "provider_name": provider[3],
        "subscriber_last_name": subscriber[3],
        "subscriber_first_name": subscriber[4],
        "member_id": member_id,
        "trace_number": trace_number,
        "eligibility_date": eligibility_date_segment[3],
        "eligibility_status": eligibility_status,
        "benefit_code": benefit_code,
    }