from __future__ import annotations

from pathlib import Path

import pydicom
import requests


ORTHANC_BASE_URL = "http://127.0.0.1:8042"

DICOM_FILE = Path(
    "fixtures/dicom/interop-lab-test-image.dcm"
)


def load_source_dicom() -> dict:
    dataset = pydicom.dcmread(
        DICOM_FILE
    )

    return {
        "patient_id": str(dataset.PatientID),
        "patient_name": str(dataset.PatientName),
        "accession_number": str(dataset.AccessionNumber),
        "study_instance_uid": str(dataset.StudyInstanceUID),
        "series_instance_uid": str(dataset.SeriesInstanceUID),
        "sop_instance_uid": str(dataset.SOPInstanceUID),
        "modality": str(dataset.Modality),
        "study_description": str(dataset.StudyDescription),
        "series_description": str(dataset.SeriesDescription),
    }


def get_json(path: str):
    response = requests.get(
        f"{ORTHANC_BASE_URL}{path}",
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def find_study_by_patient_id(
    patient_id: str,
) -> dict:
    study_ids = get_json(
        "/studies"
    )

    for study_id in study_ids:
        study = get_json(
            f"/studies/{study_id}"
        )

        tags = study.get(
            "PatientMainDicomTags",
            {},
        )

        if tags.get("PatientID") == patient_id:
            return study

    raise AssertionError(
        f"No Orthanc study found for "
        f"PatientID={patient_id}"
    )


def build_reconciliation_report() -> dict:
    source = load_source_dicom()

    study = find_study_by_patient_id(
        source["patient_id"]
    )

    study_tags = study.get(
        "MainDicomTags",
        {},
    )

    patient_tags = study.get(
        "PatientMainDicomTags",
        {},
    )

    series_ids = study.get(
        "Series",
        [],
    )

    assert len(series_ids) == 1, (
        "Expected exactly one series "
        f"but found {len(series_ids)}."
    )

    series = get_json(
        f"/series/{series_ids[0]}"
    )

    series_tags = series.get(
        "MainDicomTags",
        {},
    )

    instance_ids = series.get(
        "Instances",
        [],
    )

    assert len(instance_ids) == 1, (
        "Expected exactly one instance "
        f"but found {len(instance_ids)}."
    )

    instance = get_json(
        f"/instances/{instance_ids[0]}"
    )

    instance_tags = instance.get(
        "MainDicomTags",
        {},
    )

    checks = {
        "patient_id_preserved": (
            patient_tags.get("PatientID")
            == source["patient_id"]
        ),

        "patient_name_preserved": (
            patient_tags.get("PatientName")
            == source["patient_name"]
        ),

        "accession_number_preserved": (
            study_tags.get("AccessionNumber")
            == source["accession_number"]
        ),

        "study_uid_preserved": (
            study_tags.get("StudyInstanceUID")
            == source["study_instance_uid"]
        ),

        "study_description_preserved": (
            study_tags.get("StudyDescription")
            == source["study_description"]
        ),

        "series_uid_preserved": (
            series_tags.get("SeriesInstanceUID")
            == source["series_instance_uid"]
        ),

        "series_description_preserved": (
            series_tags.get("SeriesDescription")
            == source["series_description"]
        ),

        "modality_preserved": (
            series_tags.get("Modality")
            == source["modality"]
        ),

        "sop_instance_uid_preserved": (
            instance_tags.get("SOPInstanceUID")
            == source["sop_instance_uid"]
        ),
    }

    return {
        "source": source,
        "checks": checks,
        "passed": all(
            checks.values()
        ),
    }


def main() -> None:
    result = build_reconciliation_report()

    source = result["source"]

    print()
    print("DICOM SOURCE -> PACS RECONCILIATION")
    print("-----------------------------------")

    print(
        f"Patient ID:       "
        f"{source['patient_id']}"
    )

    print(
        f"Accession:        "
        f"{source['accession_number']}"
    )

    print(
        f"Modality:         "
        f"{source['modality']}"
    )

    print(
        f"Study UID:        "
        f"{source['study_instance_uid']}"
    )

    print(
        f"Series UID:       "
        f"{source['series_instance_uid']}"
    )

    print(
        f"SOP Instance UID: "
        f"{source['sop_instance_uid']}"
    )

    print()
    print("RECONCILIATION CHECKS")
    print("---------------------")

    for name, passed in result[
        "checks"
    ].items():
        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{status}: {name}"
        )

    print()
    print(
        "OVERALL: "
        + (
            "PASS"
            if result["passed"]
            else "FAIL"
        )
    )


if __name__ == "__main__":
    main()