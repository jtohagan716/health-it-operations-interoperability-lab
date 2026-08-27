from pathlib import Path

from scripts.radiology.persist_lineage import (
    delete_radiology_workflow,
    persist_radiology_lineage,
    run_interop_db_sql,
)
from scripts.radiology.orthanc_lineage_reconciliation import (
    reconcile_and_persist_radiology_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "orm-rad-workflow-000001.hl7"
)

DICOM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "dicom-rad-workflow-000001.dcm"
)

ORU_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "radiology"
    / "oru-rad-workflow-000001.hl7"
)


def test_radiology_workflow_persists_and_reconciles_with_pacs():
    """
    End-to-end operational acceptance test.

    The canonical ORM + DICOM + ORU workflow must:

    1. validate as one clinical radiology workflow,
    2. persist as one canonical PostgreSQL record,
    3. reconcile against the running Orthanc PACS,
    4. transition from PENDING to RECONCILED,
    5. preserve the expected Orthanc study identity.
    """

    workflow_id = None

    try:
        # -----------------------------------------------------
        # Establish canonical clinical workflow
        # -----------------------------------------------------

        workflow_id = persist_radiology_lineage(
            ORM_FIXTURE,
            DICOM_FIXTURE,
            ORU_FIXTURE,
        )

        assert workflow_id > 0

        # -----------------------------------------------------
        # Before PACS reconciliation, the workflow should
        # already be clinically MATCHED but operationally
        # PENDING.
        # -----------------------------------------------------

        before = run_interop_db_sql(
            f"""
SELECT
    lineage_status,
    pacs_reconciliation_status,
    COALESCE(orthanc_study_id, '')
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        assert before == (
            "MATCHED|PENDING|"
        )

        # -----------------------------------------------------
        # Reconcile canonical clinical lineage against the
        # actual study stored in the live Orthanc PACS.
        # -----------------------------------------------------

        reconciliation = (
            reconcile_and_persist_radiology_workflow(
                workflow_id,
                ORM_FIXTURE,
                DICOM_FIXTURE,
                ORU_FIXTURE,
            )
        )

        assert reconciliation["passed"] is True

        # -----------------------------------------------------
        # Every runtime PACS identity check must have passed.
        # -----------------------------------------------------

        assert reconciliation["checks"] == {
            "patient_id_preserved": True,
            "accession_number_preserved": True,
            "study_uid_preserved": True,
            "study_description_preserved": True,
            "modality_preserved": True,
        }

        # -----------------------------------------------------
        # PostgreSQL should now contain durable operational
        # evidence that PACS reconciliation succeeded.
        # -----------------------------------------------------

        after = run_interop_db_sql(
            f"""
SELECT
    lineage_status,
    pacs_reconciliation_status,
    orthanc_study_id,
    CASE
        WHEN pacs_reconciled_at IS NOT NULL
        THEN 'TIMESTAMP_PRESENT'
        ELSE 'TIMESTAMP_MISSING'
    END
FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {workflow_id};
""".strip()
        )

        fields = after.split("|")

        assert fields[0] == "MATCHED"
        assert fields[1] == "RECONCILED"

        assert (
            fields[2]
            == (
                "d14a8e7c-0a6a0855-"
                "a4cd6cea-233bb911-936cd4a1"
            )
        )

        assert (
            fields[3]
            == "TIMESTAMP_PRESENT"
        )

    finally:
        if workflow_id is not None:
            delete_radiology_workflow(
                workflow_id
            )