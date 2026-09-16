from pathlib import Path

import pytest

from scripts.hl7.oru_scenario import (
    build_oru_segments,
    load_scenario,
    validate_scenario,
)


DELIVERY_SCENARIO_PATH = Path(
    "examples/radiology/openemr-order-107/"
    "openemr-result-delivery.json"
)


def scenario(value_type="TX"):
    return {
        "scenario_id": "radiology-final",
        "message": {
            "timestamp": "20260915230000",
            "control_id": "RAD-ORU-DELIVERY-001",
            "sending_application": "RADSYSTEM",
            "sending_facility": "INTEROPLAB",
        },
        "patient": {
            "identifier": "SYNTHMRN000005",
            "family_name": "Patient005",
            "given_name": "Synthetic005",
            "date_of_birth": "20000202",
            "administrative_sex": "M",
        },
        "order": {
            "placer_number": "OEMRRAD00000107",
            "filler_number": "RAD00000107",
            "service_code": "XRCH2",
            "service_display": "Chest X-ray 2 Views",
            "observation_timestamp": "20260915224500",
            "result_status": "F",
        },
        "observations": [
            {
                "value_type": value_type,
                "code": "IMPRESSION",
                "display": "Radiology Impression",
                "coding_system": "99INTEROP",
                "value": (
                    "No acute cardiopulmonary abnormality."
                ),
                "units": "",
                "reference_range": "",
                "abnormal_flag": "",
                "result_status": "F",
            }
        ],
        "expected": {"ack_code": "AA"},
    }


def test_persisted_delivery_scenario_matches_final_workflow():
    payload = load_scenario(DELIVERY_SCENARIO_PATH)

    validate_scenario(payload)

    assert payload["patient"]["identifier"] == (
        "SYNTHMRN000005"
    )
    assert payload["order"]["placer_number"] == (
        "OEMRRAD00000107"
    )
    assert payload["order"]["filler_number"] == (
        "RAD00000107"
    )
    assert payload["order"]["service_code"] == "XRCH2"
    assert payload["observations"] == [
        {
            "value_type": "TX",
            "code": "IMPRESSION",
            "display": "Radiology Impression",
            "value": (
                "No acute cardiopulmonary abnormality."
            ),
            "units": "",
            "reference_range": "",
            "abnormal_flag": "",
            "result_status": "F",
            "coding_system": "99INTEROP",
        }
    ]


def test_text_result_allows_blank_quantitative_fields():
    payload = scenario()

    validate_scenario(payload)

    segments = build_oru_segments(payload)
    obx = next(
        segment
        for segment in segments
        if segment.startswith("OBX|")
    )
    fields = obx.split("|")

    assert fields[2] == "TX"
    assert fields[3] == (
        "IMPRESSION^Radiology Impression^99INTEROP"
    )
    assert fields[5] == (
        "No acute cardiopulmonary abnormality."
    )
    assert fields[6:9] == ["", "", ""]
    assert fields[11] == "F"


@pytest.mark.parametrize(
    "field",
    ["units", "reference_range", "abnormal_flag"],
)
def test_numeric_result_retains_quantitative_requirements(
    field,
):
    payload = scenario(value_type="NM")
    observation = payload["observations"][0]

    observation["units"] = "mg/dL"
    observation["reference_range"] = "70-99"
    observation["abnormal_flag"] = "N"
    observation[field] = ""

    with pytest.raises(
        ValueError,
        match=field,
    ):
        validate_scenario(payload)


@pytest.mark.parametrize(
    "field",
    ["code", "display", "value", "result_status"],
)
def test_text_result_still_requires_semantic_fields(field):
    payload = scenario()
    observation = payload["observations"][0]

    observation["units"] = "not-applicable"
    observation["reference_range"] = "not-applicable"
    observation["abnormal_flag"] = "N"
    observation[field] = ""

    with pytest.raises(
        ValueError,
        match=field,
    ):
        validate_scenario(payload)
