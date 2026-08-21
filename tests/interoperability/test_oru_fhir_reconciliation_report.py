from scripts.fhir.oru_fhir_reconciliation_report import (
    build_reconciliation_report,
)


def test_oru_fhir_reconciliation_report_passes():
    result = build_reconciliation_report()

    assert result["passed"] is True

    assert all(
        result["checks"].values()
    )

    assert (
        result["source_control_id"]
        == "LAB-ORU-000001"
    )

    assert (
        result["patient_id"]
        == "LAB000001"
    )

    assert (
        result["observation_code"]
        == "2345-7"
    )

    assert (
        result["observation_value"]
        == "105"
    )