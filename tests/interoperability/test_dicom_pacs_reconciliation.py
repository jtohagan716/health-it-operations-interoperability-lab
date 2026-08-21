from scripts.dicom.orthanc_reconciliation import (
    build_reconciliation_report,
)


def test_dicom_source_matches_pacs_after_ingestion():
    result = build_reconciliation_report()

    assert result["passed"] is True

    assert all(
        result["checks"].values()
    )

    source = result["source"]

    assert source["patient_id"] == "IMG000001"
    assert source["accession_number"] == "RAD000001"
    assert source["modality"] == "OT"


def test_dicom_identity_and_hierarchy_are_preserved():
    result = build_reconciliation_report()

    checks = result["checks"]

    assert checks["patient_id_preserved"]
    assert checks["accession_number_preserved"]

    assert checks["study_uid_preserved"]
    assert checks["series_uid_preserved"]
    assert checks["sop_instance_uid_preserved"]


def test_dicom_clinical_metadata_is_preserved():
    result = build_reconciliation_report()

    checks = result["checks"]

    assert checks["patient_name_preserved"]
    assert checks["study_description_preserved"]
    assert checks["series_description_preserved"]
    assert checks["modality_preserved"]