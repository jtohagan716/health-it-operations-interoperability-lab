from __future__ import annotations
from scripts.fhir.hl7_datetime import (
    hl7_ts_to_fhir_datetime,
)


LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"

OBSERVATION_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/"
    "CodeSystem/observation-category"
)

OBSERVATION_INTERPRETATION_SYSTEM = (
    "http://terminology.hl7.org/"
    "CodeSystem/v3-ObservationInterpretation"
)


FHIR_STATUS_MAP = {
    "F": "final",
    "P": "preliminary",
    "C": "corrected",
}


FHIR_INTERPRETATION_MAP = {
    "H": ("H", "High"),
    "L": ("L", "Low"),
    "HH": ("HH", "Critical high"),
    "LL": ("LL", "Critical low"),
    "N": ("N", "Normal"),
}


def map_oru_to_fhir_observation(
    oru: dict,
) -> dict:
    """
    Map the validated laboratory-result context extracted
    from an HL7 ORU^R01 message into a FHIR Observation.

    Current lab contract:
      - one OBX
      - NM value type
      - LOINC observation code
    """

    if oru["value_type"] != "NM":
        raise ValueError(
            "Current mapper supports only "
            "numeric (NM) observations."
        )

    if oru["observation_coding_system"] != "LN":
        raise ValueError(
            "Current mapper requires "
            "LOINC-coded observations."
        )

    try:
        numeric_value = float(
            oru["observation_value"]
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Numeric observation contains "
            "a non-numeric OBX-5 value."
        ) from exc

    try:
        fhir_status = FHIR_STATUS_MAP[
            oru["obx_result_status"]
        ]
    except KeyError as exc:
        raise ValueError(
            "Unsupported OBX result status: "
            f"{oru['obx_result_status']}"
        ) from exc

    try:
        interpretation_code, interpretation_display = (
            FHIR_INTERPRETATION_MAP[
                oru["abnormal_flag"]
            ]
        )
    except KeyError as exc:
        raise ValueError(
            "Unsupported abnormal flag: "
            f"{oru['abnormal_flag']}"
        ) from exc

    return {
        "resourceType": "Observation",

        "status": fhir_status,

        "category": [
            {
                "coding": [
                    {
                        "system": OBSERVATION_CATEGORY_SYSTEM,
                        "code": "laboratory",
                        "display": "Laboratory",
                    }
                ]
            }
        ],

        "code": {
            "coding": [
                {
                    "system": LOINC_SYSTEM,
                    "code": oru["observation_code"],
                    "display": oru["observation_text"],
                }
            ],
            "text": oru["observation_text"],
        },

        "subject": {
            "identifier": {
                "system": (
                    "https://example.org/fhir/"
                    "sid/interoplab-mrn"
                ),
                "value": oru["patient_id"],
            }
        },

        "effectiveDateTime": (
            hl7_ts_to_fhir_datetime(
                oru["observation_datetime"]
            )
        ),

        "valueQuantity": {
            "value": numeric_value,
            "unit": oru["observation_units"],
            "system": UCUM_SYSTEM,
            "code": oru["observation_units"],
        },

        "interpretation": [
            {
                "coding": [
                    {
                        "system": (
                            OBSERVATION_INTERPRETATION_SYSTEM
                        ),
                        "code": interpretation_code,
                        "display": interpretation_display,
                    }
                ]
            }
        ],

        "referenceRange": [
            {
                "text": oru["reference_range"]
            }
        ],

        "identifier": [
            {
                "system": (
                    "https://example.org/fhir/"
                    "sid/interoplab-observation"
                ),
                "value": (
                    f"{oru['filler_order_number']}"
                    f"-{oru['obx_set_id']}"
                ),
            }
        ],
    }