from __future__ import annotations
from scripts.fhir.hl7_datetime import (
    hl7_ts_to_fhir_datetime,
)


FHIR_STATUS_MAP = {
    "F": "final",
    "P": "preliminary",
    "C": "corrected",
}


def map_oru_to_fhir_diagnostic_report(
    oru: dict,
    observation_reference: str,
) -> dict:
    try:
        fhir_status = FHIR_STATUS_MAP[
            oru["obr_result_status"]
        ]
    except KeyError as exc:
        raise ValueError(
            "Unsupported OBR result status: "
            f"{oru['obr_result_status']}"
        ) from exc

    return {
        "resourceType": "DiagnosticReport",

        "status": fhir_status,

        "category": [
            {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/"
                            "CodeSystem/v2-0074"
                        ),
                        "code": "LAB",
                        "display": "Laboratory",
                    }
                ]
            }
        ],

        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": oru["service_code"],
                    "display": oru["service_text"],
                }
            ],
            "text": oru["service_text"],
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

        "identifier": [
            {
                "system": (
                    "https://example.org/fhir/"
                    "sid/interoplab-report"
                ),
                "value": oru[
                    "filler_order_number"
                ],
            }
        ],

        "basedOn": [
            {
                "identifier": {
                    "system": (
                        "https://example.org/fhir/"
                        "sid/interoplab-order"
                    ),
                    "value": oru[
                        "placer_order_number"
                    ],
                }
            }
        ],

        "result": [
            {
                "reference": (
                    observation_reference
                )
            }
        ],
    }