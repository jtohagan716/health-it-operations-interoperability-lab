from pathlib import Path

from scripts.hl7.analyze_oru import analyze_oru
from scripts.fhir.map_oru_to_observation import (
    map_oru_to_fhir_observation,
)
from scripts.fhir.map_oru_to_diagnostic_report import (
    map_oru_to_fhir_diagnostic_report,
)


HL7_FIXTURE = Path(
    "fixtures/hl7/oru/oru-r01-lab000001.hl7"
)


def test_oru_maps_to_coherent_fhir_result_graph():
    oru = analyze_oru(HL7_FIXTURE)

    observation = map_oru_to_fhir_observation(
        oru
    )

    observation_reference = (
        "Observation/"
        + observation["identifier"][0]["value"]
    )

    report = map_oru_to_fhir_diagnostic_report(
        oru,
        observation_reference=observation_reference,
    )

    # ---------------------------------------------------------
    # RESOURCE TYPES
    # ---------------------------------------------------------

    assert (
        observation["resourceType"]
        == "Observation"
    )

    assert (
        report["resourceType"]
        == "DiagnosticReport"
    )

    # ---------------------------------------------------------
    # PATIENT IDENTITY AGREEMENT
    # ---------------------------------------------------------

    observation_patient = (
        observation["subject"]
        ["identifier"]["value"]
    )

    report_patient = (
        report["subject"]
        ["identifier"]["value"]
    )

    assert observation_patient == oru["patient_id"]
    assert report_patient == oru["patient_id"]
    assert observation_patient == report_patient

    # ---------------------------------------------------------
    # CLINICAL CODE AGREEMENT
    # ---------------------------------------------------------

    observation_code = (
        observation["code"]
        ["coding"][0]["code"]
    )

    report_code = (
        report["code"]
        ["coding"][0]["code"]
    )

    assert (
        observation_code
        == oru["observation_code"]
    )

    assert (
        report_code
        == oru["service_code"]
    )

    assert observation_code == report_code

    # ---------------------------------------------------------
    # RESULT VALUE / UNITS / INTERPRETATION
    # ---------------------------------------------------------

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

    assert (
        observation["interpretation"][0]
        ["coding"][0]["code"]
        == oru["abnormal_flag"]
    )

    # ---------------------------------------------------------
    # STATUS AGREEMENT
    # ---------------------------------------------------------

    assert observation["status"] == "final"
    assert report["status"] == "final"

    # ---------------------------------------------------------
    # ORDER / REPORT IDENTITY
    # ---------------------------------------------------------

    assert (
        report["identifier"][0]["value"]
        == oru["filler_order_number"]
    )

    assert (
        report["basedOn"][0]
        ["identifier"]["value"]
        == oru["placer_order_number"]
    )

    # ---------------------------------------------------------
    # GRAPH LINKAGE
    # ---------------------------------------------------------

    assert (
        report["result"][0]["reference"]
        == observation_reference
    )

    assert (
        observation_reference
        == "Observation/LABRPT000001-1"
    )