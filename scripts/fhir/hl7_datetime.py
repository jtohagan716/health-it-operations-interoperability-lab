from __future__ import annotations

from datetime import datetime


HL7_TIMESTAMP_FORMATS = (
    "%Y%m%d%H%M%S%z",
    "%Y%m%d%H%M%S",
    "%Y%m%d%H%M",
    "%Y%m%d",
)


def hl7_ts_to_fhir_datetime(
    value: str,
) -> str:
    """
    Convert an HL7 v2 TS value into a FHIR-compatible
    ISO-8601 dateTime representation.
    """

    if not value:
        raise ValueError(
            "HL7 timestamp is required."
        )

    for format_string in HL7_TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(
                value,
                format_string,
            )
            break
        except ValueError:
            continue
    else:
        raise ValueError(
            f"Unsupported HL7 timestamp: {value}"
        )

    if parsed.tzinfo is not None:
        return parsed.isoformat(
            timespec="seconds"
        )

    if len(value) == 8:
        return parsed.date().isoformat()

    return parsed.isoformat(
        timespec="seconds"
    )