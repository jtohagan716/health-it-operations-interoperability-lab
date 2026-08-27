from __future__ import annotations

from pathlib import Path

import pydicom
import requests

from scripts.hl7.analyze_orm import analyze_orm
from scripts.hl7.analyze_radiology_oru import (
    analyze_radiology_oru,
)
from scripts.radiology.lineage import (
    validate_full_radiology_lineage,
)
from scripts.radiology.persist_lineage import (
    run_interop_db_sql,
    sql_literal,
)


ORTHANC_BASE_URL = "http://127.0.0.1:8042"


def get_json(
    path: str,
):
    """
    Retrieve JSON from the local Orthanc REST API.
    """

    response = requests.get(
        f"{ORTHANC_BASE_URL}{path}",
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def find_orthanc_study_by_patient_id(
    patient_id: str,
) -> dict:
    """
    Find exactly one Orthanc study for the supplied patient.

    This controlled lab currently expects one canonical
    radiology study for the synthetic workflow patient.
    """

    study_ids = get_json(
        "/studies"
    )

    matches = []

    for study_id in study_ids:
        study = get_json(
            f"/studies/{study_id}"
        )

        patient_tags = study.get(
            "PatientMainDicomTags",
            {},
        )

        if (
            patient_tags.get("PatientID")
            == patient_id
        ):
            matches.append(
                study
            )

    if not matches:
        raise ValueError(
            "No Orthanc study found for "
            f"PatientID={patient_id}"
        )

    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one Orthanc study for "
            f"PatientID={patient_id}, "
            f"found {len(matches)}"
        )

    return matches[0]


def reconcile_radiology_workflow_to_orthanc(
    orm_path: Path,
    dicom_path: Path,
    oru_path: Path,
) -> dict:
    """
    Validate the canonical ORM -> DICOM -> ORU radiology
    lineage and reconcile it against the live Orthanc PACS.

    The result contains:
        lineage
        orthanc_study
        checks
        passed
    """

    orm = analyze_orm(
        orm_path
    )

    source_dicom = pydicom.dcmread(
        dicom_path,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        oru_path
    )

    lineage = validate_full_radiology_lineage(
        orm,
        source_dicom,
        oru,
    )

    orthanc_study = (
        find_orthanc_study_by_patient_id(
            lineage.patient_id
        )
    )

    study_tags = orthanc_study.get(
        "MainDicomTags",
        {},
    )

    patient_tags = orthanc_study.get(
        "PatientMainDicomTags",
        {},
    )

    series_ids = orthanc_study.get(
        "Series",
        [],
    )

    if len(series_ids) != 1:
        raise ValueError(
            "Expected exactly one Orthanc series "
            f"but found {len(series_ids)}."
        )

    series = get_json(
        f"/series/{series_ids[0]}"
    )

    series_tags = series.get(
        "MainDicomTags",
        {},
    )

    checks = {
        "patient_id_preserved":
            patient_tags.get("PatientID")
            == lineage.patient_id,

        "accession_number_preserved":
            study_tags.get("AccessionNumber")
            == lineage.accession_number,

        "study_uid_preserved":
            study_tags.get("StudyInstanceUID")
            == lineage.study_instance_uid,

        "study_description_preserved":
            study_tags.get("StudyDescription")
            == lineage.procedure_text,

        "modality_preserved":
            series_tags.get("Modality")
            == lineage.modality,
    }

    return {
        "lineage": lineage,
        "orthanc_study": orthanc_study,
        "checks": checks,
        "passed": all(
            checks.values()
        ),
    }


def persist_pacs_reconciliation(
    radiology_workflow_id: int,
    reconciliation: dict,
) -> None:
    """
    Persist the outcome of PACS reconciliation.

    Successful reconciliation:
        pacs_reconciliation_status = RECONCILED
        pacs_reconciled_at = current timestamp

    Failed reconciliation:
        pacs_reconciliation_status = FAILED
        pacs_reconciled_at = NULL
        diagnostic failure detail is preserved
    """

    orthanc_study = reconciliation.get(
        "orthanc_study",
        {},
    )

    orthanc_study_id = orthanc_study.get(
        "ID"
    )

    passed = bool(
        reconciliation.get(
            "passed",
            False,
        )
    )

    status = (
        "RECONCILED"
        if passed
        else "FAILED"
    )

    failed_checks = [
        name
        for name, check_passed
        in reconciliation.get(
            "checks",
            {},
        ).items()
        if not check_passed
    ]

    if passed:
        detail = (
            "Live Orthanc PACS metadata matched "
            "the canonical radiology workflow."
        )

        reconciled_at_sql = (
            "CURRENT_TIMESTAMP"
        )

    else:
        detail = (
            "PACS reconciliation failed"
        )

        if failed_checks:
            detail += (
                ": "
                + ", ".join(
                    failed_checks
                )
            )

        reconciled_at_sql = "NULL"

    sql = f"""
UPDATE audit.radiology_workflows
SET
    orthanc_study_id =
        {sql_literal(orthanc_study_id)},
    pacs_reconciliation_status =
        {sql_literal(status)},
    pacs_reconciliation_detail =
        {sql_literal(detail)},
    pacs_reconciled_at =
        {reconciled_at_sql}
WHERE radiology_workflow_id =
      {int(radiology_workflow_id)};
""".strip()

    run_interop_db_sql(
        sql
    )


def reconcile_and_persist_radiology_workflow(
    radiology_workflow_id: int,
    orm_path: Path,
    dicom_path: Path,
    oru_path: Path,
) -> dict:
    """
    Reconcile one canonical radiology workflow against the
    live Orthanc PACS and persist the resulting operational
    state.

    Returns the reconciliation result.
    """

    reconciliation = (
        reconcile_radiology_workflow_to_orthanc(
            orm_path,
            dicom_path,
            oru_path,
        )
    )

    persist_pacs_reconciliation(
        radiology_workflow_id,
        reconciliation,
    )

    return reconciliation