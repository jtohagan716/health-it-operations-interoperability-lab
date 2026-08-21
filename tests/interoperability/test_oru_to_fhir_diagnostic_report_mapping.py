from pathlib import Path

import pytest

from scripts.hl7.analyze_oru import analyze_oru
from scripts.fhir.map_oru_to_diagnostic_report import (
    map_oru_to_fhir_diagnostic_report,
)


HL7_FIXTURE = Path(
    "fixtures/hl7/oru/oru-r01-lab000001.hl7"
)


def test_maps_oru_to_fhir_diagnostic_report():
    oru = analyze_oru(HL7_FIXTURE)

    report = map_oru_to_fhir_diagnostic_report(
        oru,
        observation_reference=(
            "Observation/LABRPT000001-1"
        ),
    )

    assert (
    report["effectiveDateTime"]
    == "2026-08-20T15:00:00-04:00"
    )

    assert report["resourceType"] == "DiagnosticReport"
    assert report["status"] == "final"

    coding = report["code"]["coding"][0]

    assert coding["system"] == "http://loinc.org"
    assert coding["code"] == "2345-7"
    assert coding["display"] == "Glucose"

    assert (
        report["subject"]["identifier"]["value"]
        == "LAB000001"
    )

    assert (
        report["identifier"][0]["value"]
        == "LABRPT000001"
    )

    assert (
        report["basedOn"][0]
        ["identifier"]["value"]
        == "ORD000001"
    )

    assert (
        report["result"][0]["reference"]
        == "Observation/LABRPT000001-1"
    )


def test_diagnostic_report_preserves_source_semantics():
    oru = analyze_oru(HL7_FIXTURE)

    report = map_oru_to_fhir_diagnostic_report(
        oru,
        observation_reference="Observation/example",
    )

    assert (
        report["code"]["coding"][0]["code"]
        == oru["service_code"]
    )

    assert (
        report["identifier"][0]["value"]
        == oru["filler_order_number"]
    )

    assert (
        report["basedOn"][0]
        ["identifier"]["value"]
        == oru["placer_order_number"]
    )


def test_rejects_unsupported_obr_status(
    tmp_path,
):
    source = HL7_FIXTURE.read_text(
        encoding="utf-8"
    )

    modified = source.replace(
        "||||||||||||||||||F",
        "||||||||||||||||||X",
        1,
    )

    fixture = (
        tmp_path
        / "oru-unsupported-obr-status.hl7"
    )

    fixture.write_text(
        modified,
        encoding="utf-8",
    )

    oru = analyze_oru(fixture)

    with pytest.raises(
        ValueError,
        match="Unsupported OBR result status",
    ):
        map_oru_to_fhir_diagnostic_report(
            oru,
            observation_reference="Observation/example",
        )