from pathlib import Path

import pytest

from scripts.hl7.analyze_oru import analyze_oru
from scripts.fhir.map_oru_to_observation import (
    map_oru_to_fhir_observation,
)


HL7_FIXTURE = Path(
    "fixtures/hl7/oru/oru-r01-lab000001.hl7"
)


def test_maps_oru_glucose_to_fhir_observation():
    oru = analyze_oru(HL7_FIXTURE)

    observation = map_oru_to_fhir_observation(
        oru
    )

    assert observation["resourceType"] == "Observation"
    assert observation["status"] == "final"

    category = observation["category"][0]["coding"][0]

    assert category["code"] == "laboratory"

    coding = observation["code"]["coding"][0]

    assert coding["system"] == "http://loinc.org"
    assert coding["code"] == "2345-7"
    assert coding["display"] == "Glucose"

    subject_identifier = (
        observation["subject"]["identifier"]
    )

    assert (
        subject_identifier["value"]
        == "LAB000001"
    )

    quantity = observation["valueQuantity"]

    assert quantity["value"] == 105.0
    assert quantity["unit"] == "mg/dL"

    interpretation = (
        observation["interpretation"][0]
        ["coding"][0]
    )

    assert interpretation["code"] == "H"
    assert interpretation["display"] == "High"

    assert (
        observation["referenceRange"][0]["text"]
        == "70-99"
    )

    assert (
        observation["identifier"][0]["value"]
        == "LABRPT000001-1"
    )


def test_observation_mapping_preserves_source_semantics():
    oru = analyze_oru(HL7_FIXTURE)

    observation = map_oru_to_fhir_observation(
        oru
    )

    assert (
        observation["code"]["coding"][0]["code"]
        == oru["observation_code"]
    )

    assert (
        observation["code"]["coding"][0]["display"]
        == oru["observation_text"]
    )

    assert (
        observation["valueQuantity"]["value"]
        == float(oru["observation_value"])
    )

    assert (
        observation["valueQuantity"]["unit"]
        == oru["observation_units"]
    )

    assert (
        observation["referenceRange"][0]["text"]
        == oru["reference_range"]
    )


def test_rejects_non_numeric_nm_observation(
    tmp_path,
):
    source = HL7_FIXTURE.read_text(
        encoding="utf-8"
    )

    modified = source.replace(
        "||105|mg/dL|",
        "||ABC|mg/dL|",
        1,
    )

    fixture = (
        tmp_path
        / "oru-invalid-numeric.hl7"
    )

    fixture.write_text(
        modified,
        encoding="utf-8",
    )

    oru = analyze_oru(fixture)

    with pytest.raises(
        ValueError,
        match="non-numeric OBX-5",
    ):
        map_oru_to_fhir_observation(
            oru
        )


def test_rejects_unsupported_obx_status(
    tmp_path,
):
    source = HL7_FIXTURE.read_text(
        encoding="utf-8"
    )

    modified = source.replace(
        "|70-99|H|||F",
        "|70-99|H|||X",
        1,
    )

    fixture = (
        tmp_path
        / "oru-unsupported-status.hl7"
    )

    fixture.write_text(
        modified,
        encoding="utf-8",
    )

    oru = analyze_oru(fixture)

    with pytest.raises(
        ValueError,
        match="Unsupported OBX result status",
    ):
        map_oru_to_fhir_observation(
            oru
        )

def test_rejects_semantically_wrong_loinc_display(
    tmp_path,
):
    source = HL7_FIXTURE.read_text(
        encoding="utf-8"
    )

    modified = source.replace(
        "2345-7^Glucose^LN",
        "2345-7^Potassium^LN",
    )

    fixture = (
        tmp_path
        / "oru-wrong-loinc-display.hl7"
    )

    fixture.write_text(
        modified,
        encoding="utf-8",
    )

    oru = analyze_oru(fixture)

    with pytest.raises(
        ValueError,
        match="LOINC semantic mismatch",
    ):
        map_oru_to_fhir_observation(
            oru
        )