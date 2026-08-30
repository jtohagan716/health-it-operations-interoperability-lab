from __future__ import annotations


LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"


LAB_TERMINOLOGY = {
    "2345-7": {
        "display": "Glucose",
        "canonical_display": (
            "Glucose [Mass/volume] in Serum or Plasma"
        ),
        "allowed_ucum_units": {"mg/dL"},
    },
}


def validate_lab_observation_terminology(
    *,
    code: str,
    display: str,
    coding_system: str,
    unit: str,
) -> None:
    """
    Validate the terminology semantics used by the
    interoperability lab's supported observations.

    This intentionally verifies meaning, not merely
    that fields are populated.
    """

    if coding_system != "LN":
        raise ValueError(
            "Expected HL7 v2 coding system LN "
            f"for LOINC, got {coding_system!r}."
        )

    concept = LAB_TERMINOLOGY.get(code)

    if concept is None:
        raise ValueError(
            f"Unsupported or unknown LOINC code: {code!r}."
        )

    if display != concept["display"]:
        raise ValueError(
            "LOINC semantic mismatch: "
            f"{code!r} is expected to represent "
            f"{concept['display']!r}, got {display!r}."
        )

    if unit not in concept["allowed_ucum_units"]:
        raise ValueError(
            "UCUM unit mismatch for LOINC "
            f"{code!r}: got {unit!r}; "
            "allowed units are "
            f"{sorted(concept['allowed_ucum_units'])!r}."
        )