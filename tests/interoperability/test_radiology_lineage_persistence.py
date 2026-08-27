from pathlib import Path
import uuid

import pydicom
import pytest

from pydicom.uid import generate_uid

from scripts.radiology.persist_lineage import (
    delete_radiology_workflow,
    persist_radiology_lineage,
    run_interop_db_sql,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_ORM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "orm-rad-workflow-000001.hl7"
)

BASE_DICOM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "dicom-rad-workflow-000001.dcm"
)

BASE_ORU_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "oru-rad-workflow-000001.hl7"
)


def create_isolated_radiology_workflow(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    dict[str, str],
]:
    """
    Create a disposable, internally consistent
    ORM + DICOM + ORU radiology workflow.

    Every workflow identity is unique to this test run.

    This prevents persistence tests from ever reusing or
    deleting the permanent documentation workflow.
    """

    suffix = uuid.uuid4().hex[:6].upper()

    patient_id = (
        f"RADP{suffix}"
    )

    placer_order = (
        f"RADORD{suffix}"
    )

    accession = (
        f"RAD{suffix}"
    )

    orm_control_id = (
        f"RAD-ORM-PERSIST-{suffix}"
    )

    oru_control_id = (
        f"RAD-ORU-PERSIST-{suffix}"
    )

    study_uid = generate_uid()
    series_uid = generate_uid()
    sop_uid = generate_uid()

    # ---------------------------------------------------------
    # ORM
    # ---------------------------------------------------------

    orm_text = BASE_ORM_FIXTURE.read_text(
        encoding="ascii"
    )

    orm_text = orm_text.replace(
        "RAD-ORM-WORKFLOW-000001",
        orm_control_id,
    )

    orm_text = orm_text.replace(
        "RADPAT000001",
        patient_id,
    )

    orm_text = orm_text.replace(
        "RADORD000001",
        placer_order,
    )

    orm_text = orm_text.replace(
        "RAD000001",
        accession,
    )

    orm_path = (
        tmp_path
        / "orm-radiology-persistence.hl7"
    )

    orm_path.write_text(
        orm_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # ORU
    # ---------------------------------------------------------

    oru_text = BASE_ORU_FIXTURE.read_text(
        encoding="ascii"
    )

    oru_text = oru_text.replace(
        "RAD-ORU-WORKFLOW-000001",
        oru_control_id,
    )

    oru_text = oru_text.replace(
        "RADPAT000001",
        patient_id,
    )

    oru_text = oru_text.replace(
        "RADORD000001",
        placer_order,
    )

    oru_text = oru_text.replace(
        "RAD000001",
        accession,
    )

    oru_path = (
        tmp_path
        / "oru-radiology-persistence.hl7"
    )

    oru_path.write_text(
        oru_text,
        encoding="ascii",
    )

    # ---------------------------------------------------------
    # DICOM
    # ---------------------------------------------------------

    dataset = pydicom.dcmread(
        BASE_DICOM_FIXTURE
    )

    dataset.PatientID = patient_id
    dataset.AccessionNumber = accession

    dataset.StudyInstanceUID = (
        study_uid
    )

    dataset.SeriesInstanceUID = (
        series_uid
    )

    dataset.SOPInstanceUID = (
        sop_uid
    )

    dataset.file_meta.MediaStorageSOPInstanceUID = (
        sop_uid
    )

    dicom_path = (
        tmp_path
        / "dicom-radiology-persistence.dcm"
    )

    dataset.save_as(
        dicom_path,
        enforce_file_format=True,
    )

    expected = {
        "patient_id":
            patient_id,

        "placer_order":
            placer_order,

        "accession":
            accession,

        "orm_control_id":
            orm_control_id,

        "oru_control_id":
            oru_control_id,

        "study_uid":
            study_uid,

        "procedure_code":
            "XRCH2",

        "procedure_text":
            "Chest X-ray 2 Views",
    }

    return (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    )


def create_conflicting_dicom(
    source_dicom: Path,
    tmp_path: Path,
) -> Path:
    """
    Create a structurally valid conflicting DICOM study.

    The conflicting study deliberately preserves:

        accession number
        Study Instance UID

    while changing:

        PatientID

    This represents an unsafe attempt to associate the same
    imaging workflow identity with a different patient.
    """

    dataset = pydicom.dcmread(
        source_dicom
    )

    dataset.PatientID = (
        "WRONGPATIENT"
    )

    output_path = (
        tmp_path
        / "dicom-conflicting-patient.dcm"
    )

    dataset.save_as(
        output_path,
        enforce_file_format=True,
    )

    return output_path


def test_radiology_lineage_persistence_is_idempotent(
    tmp_path: Path,
):
    """
    Repeated persistence of the exact same clinical workflow
    must reuse one canonical database row.

    The test uses a unique disposable workflow so cleanup
    cannot affect preexisting demonstration data.
    """

    workflow_id = None

    (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    ) = create_isolated_radiology_workflow(
        tmp_path
    )

    try:
        # -----------------------------------------------------
        # First persistence establishes canonical state.
        # -----------------------------------------------------

        first_id = persist_radiology_lineage(
            orm_path,
            dicom_path,
            oru_path,
        )

        workflow_id = first_id

        assert first_id > 0

        # -----------------------------------------------------
        # Exact replay of the same workflow must reuse the
        # canonical row rather than create another one.
        # -----------------------------------------------------

        second_id = persist_radiology_lineage(
            orm_path,
            dicom_path,
            oru_path,
        )

        assert (
            first_id
            == second_id
        )

        # -----------------------------------------------------
        # Verify only one workflow row exists.
        # -----------------------------------------------------

        row_count = run_interop_db_sql(
            f"""
SELECT COUNT(*)
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {first_id};
""".strip()
        )

        assert row_count == "1"

        # -----------------------------------------------------
        # Verify canonical identity was preserved.
        # -----------------------------------------------------

        persisted = run_interop_db_sql(
            f"""
SELECT
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code,
    procedure_text,
    study_instance_uid,
    lineage_status
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {first_id};
""".strip()
        )

        fields = persisted.split("|")

        assert fields == [
            expected["patient_id"],
            expected["placer_order"],
            expected["accession"],
            expected["procedure_code"],
            expected["procedure_text"],
            expected["study_uid"],
            "MATCHED",
        ]

    finally:
        # -----------------------------------------------------
        # This workflow uses identities generated exclusively
        # for this test, so this cleanup owns the row.
        # -----------------------------------------------------

        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )


def test_conflicting_radiology_identity_is_rejected(
    tmp_path: Path,
):
    """
    A workflow that reuses the same accession and Study UID
    while changing patient identity must be rejected.

    The canonical workflow must remain unchanged after the
    conflicting attempt.
    """

    workflow_id = None

    (
        orm_path,
        dicom_path,
        oru_path,
        expected,
    ) = create_isolated_radiology_workflow(
        tmp_path
    )

    try:
        # -----------------------------------------------------
        # Establish test-owned canonical state.
        # -----------------------------------------------------

        workflow_id = persist_radiology_lineage(
            orm_path,
            dicom_path,
            oru_path,
        )

        assert workflow_id > 0

        # -----------------------------------------------------
        # Create a conflicting DICOM that reuses the same
        # workflow identifiers but changes PatientID.
        # -----------------------------------------------------

        conflicting_dicom = (
            create_conflicting_dicom(
                dicom_path,
                tmp_path,
            )
        )

        # -----------------------------------------------------
        # The conflicting workflow must fail closed.
        # -----------------------------------------------------

        with pytest.raises(
            ValueError,
            match="Radiology patient identity mismatch",
        ):
            persist_radiology_lineage(
                orm_path,
                conflicting_dicom,
                oru_path,
            )

        # -----------------------------------------------------
        # Verify the canonical row was not modified.
        # -----------------------------------------------------

        canonical = run_interop_db_sql(
            f"""
SELECT
    patient_identifier,
    placer_order_number,
    accession_number,
    study_instance_uid,
    lineage_status
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        fields = canonical.split("|")

        assert fields == [
            expected["patient_id"],
            expected["placer_order"],
            expected["accession"],
            expected["study_uid"],
            "MATCHED",
        ]

        assert (
            fields[0]
            != "WRONGPATIENT"
        )

        # -----------------------------------------------------
        # Still exactly one canonical workflow.
        # -----------------------------------------------------

        row_count = run_interop_db_sql(
            f"""
SELECT COUNT(*)
FROM audit.radiology_workflows
WHERE accession_number =
      '{expected["accession"]}';
""".strip()
        )

        assert row_count == "1"

    finally:
        # -----------------------------------------------------
        # Delete only the disposable workflow created by
        # this test.
        # -----------------------------------------------------

        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )