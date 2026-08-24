from pathlib import Path


def load_x12(path: Path) -> list[list[str]]:
    """
    Load an X12 document and return each segment as a list
    of its individual elements.

    Example:

        ST*270*0001~

    becomes:

        ["ST", "270", "0001"]
    """

    raw = path.read_text(encoding="ascii").strip()

    segments = []

    for raw_segment in raw.split("~"):
        segment = raw_segment.strip()

        if not segment:
            continue

        segments.append(segment.split("*"))

    return segments


def find_segment(
    segments: list[list[str]],
    segment_id: str,
) -> list[str]:
    """
    Return exactly one segment having the requested
    segment identifier.
    """

    matches = [
        segment
        for segment in segments
        if segment[0] == segment_id
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {segment_id} segment "
            f"but found {len(matches)}."
        )

    return matches[0]


def find_segments(
    segments: list[list[str]],
    segment_id: str,
) -> list[list[str]]:
    """
    Return all segments having the requested identifier.
    """

    return [
        segment
        for segment in segments
        if segment[0] == segment_id
    ]


def validate_transaction_segment_count(
    segments: list[list[str]],
) -> None:
    """
    Validate SE01 against the actual number of segments
    from the Transaction Set Header (ST) through the
    Transaction Set Trailer (SE), inclusive.
    """

    st_index = next(
        (
            index
            for index, segment in enumerate(segments)
            if segment[0] == "ST"
        ),
        None,
    )

    se_index = next(
        (
            index
            for index, segment in enumerate(segments)
            if segment[0] == "SE"
        ),
        None,
    )

    if st_index is None:
        raise ValueError(
            "X12 transaction is missing the ST "
            "Transaction Set Header."
        )

    if se_index is None:
        raise ValueError(
            "X12 transaction is missing the SE "
            "Transaction Set Trailer."
        )

    if se_index < st_index:
        raise ValueError(
            "SE Transaction Set Trailer occurs before "
            "the ST Transaction Set Header."
        )

    se = segments[se_index]

    if len(se) <= 1 or not se[1]:
        raise ValueError(
            "SE01 transaction segment count is missing."
        )

    try:
        reported_count = int(se[1])
    except ValueError as exc:
        raise ValueError(
            "SE01 transaction segment count must be numeric."
        ) from exc

    actual_count = se_index - st_index + 1

    if reported_count != actual_count:
        raise ValueError(
            "SE transaction segment count does not match actual "
            f"segment count: {reported_count} != {actual_count}"
        )


def validate_270_envelopes(
    segments: list[list[str]],
) -> dict[str, str]:
    """
    Validate envelope and control-number integrity for a
    270 Eligibility Inquiry.

    X12 uses nested envelopes:

        ISA ... IEA
            Interchange

        GS ... GE
            Functional Group

        ST ... SE
            Transaction Set

    The control numbers at each opening and closing boundary
    must agree.
    """

    isa = find_segment(segments, "ISA")
    iea = find_segment(segments, "IEA")

    gs = find_segment(segments, "GS")
    ge = find_segment(segments, "GE")

    st = find_segment(segments, "ST")
    se = find_segment(segments, "SE")

    # ST01 identifies the transaction type.
    # 270 = Eligibility, Coverage or Benefit Inquiry.
    if st[1] != "270":
        raise ValueError(
            f"Expected transaction type 270 but found {st[1]!r}."
        )

    # ISA13 and IEA02 identify the interchange.
    isa_control = isa[13]
    iea_control = iea[2]

    if isa_control != iea_control:
        raise ValueError(
            "ISA/IEA interchange control numbers do not match: "
            f"{isa_control!r} != {iea_control!r}"
        )

    # GS06 and GE02 identify the Functional Group.
    gs_control = gs[6]
    ge_control = ge[2]

    if gs_control != ge_control:
        raise ValueError(
            "GS/GE functional-group control numbers do not match: "
            f"{gs_control!r} != {ge_control!r}"
        )

    # ST02 and SE02 identify the individual Transaction Set.
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


def parse_270_business_data(
    segments: list[list[str]],
) -> dict[str, str]:
    """
    Extract selected business information from the
    synthetic 270 Eligibility Inquiry used by this lab.

    This is intentionally a constrained lab parser rather
    than a complete implementation of the full X12
    005010X279A1 implementation guide.
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
            "270 eligibility inquiry is missing the payer."
        )

    if provider is None:
        raise ValueError(
            "270 eligibility inquiry is missing the provider."
        )

    if subscriber is None:
        raise ValueError(
            "270 eligibility inquiry is missing the subscriber."
        )

    member_id = (
        subscriber[9]
        if len(subscriber) > 9
        else ""
    )

    if not member_id:
        raise ValueError(
            "270 eligibility inquiry is missing the "
            "subscriber member ID."
        )

    # TRN = Trace segment.
    # TRN02 is our business correlation identifier.
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
            "270 eligibility inquiry is missing the trace number."
        )

    # DTP = Date or Time Period.
    # Qualifier 291 is the eligibility-related date in our lab.
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
            "270 eligibility inquiry is missing the "
            "eligibility date."
        )

    # EQ = Eligibility or Benefit Inquiry.
    # This describes what category of benefit information
    # the provider is asking the payer about.
    eq = find_segment(
        segments,
        "EQ",
    )

    benefit_code = (
        eq[1]
        if len(eq) > 1
        else ""
    )

    if not benefit_code:
        raise ValueError(
            "270 eligibility inquiry is missing the benefit code."
        )

    return {
        "payer_name": payer[3],
        "provider_name": provider[3],
        "subscriber_last_name": subscriber[3],
        "subscriber_first_name": subscriber[4],
        "member_id": member_id,
        "trace_number": trace_number,
        "eligibility_date": eligibility_date_segment[3],
        "benefit_code": benefit_code,
    }