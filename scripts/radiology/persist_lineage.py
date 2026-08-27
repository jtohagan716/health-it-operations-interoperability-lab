from __future__ import annotations

import subprocess
from pathlib import Path

import pydicom

from scripts.hl7.analyze_orm import analyze_orm
from scripts.hl7.analyze_radiology_oru import (
    analyze_radiology_oru,
)
from scripts.radiology.lineage import (
    RadiologyLineageResult,
    validate_full_radiology_lineage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIRTH_ENV = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / ".env"
)

MIRTH_COMPOSE = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "compose.yaml"
)


def load_env_file(
    path: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}

    for raw_line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        values[key.strip()] = value.strip()

    return values


def sql_literal(
    value: str | None,
) -> str:
    if value is None:
        return "NULL"

    escaped = value.replace(
        "'",
        "''",
    )

    return f"'{escaped}'"


def run_interop_db_sql(
    sql: str,
) -> str:
    """
    Execute SQL against the PostgreSQL interoperability
    database running in Docker.
    """

    env_values = load_env_file(
        MIRTH_ENV
    )

    db_user = env_values[
        "INTEROP_DB_USER"
    ]

    db_name = env_values[
        "INTEROP_DB_NAME"
    ]

    command = [
        "docker",
        "compose",
        "--env-file",
        str(MIRTH_ENV),
        "-f",
        str(MIRTH_COMPOSE),
        "exec",
        "-T",
        "interop-db",
        "psql",
        "-U",
        db_user,
        "-d",
        db_name,
        "-t",
        "-A",
        "-c",
        sql,
    ]

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Radiology persistence SQL failed:\n"
            f"{result.stderr}"
        )

    return result.stdout.strip()


def build_expected_record(
    lineage: RadiologyLineageResult,
    oru: dict,
) -> dict[str, str]:
    return {
        "patient_identifier":
            lineage.patient_id,

        "placer_order_number":
            lineage.placer_order_number,

        "accession_number":
            lineage.accession_number,

        "procedure_code":
            lineage.procedure_code,

        "procedure_text":
            lineage.procedure_text,

        "study_instance_uid":
            lineage.study_instance_uid,

        "modality":
            lineage.modality,

        "oru_message_control_id":
            oru["message_control_id"],

        "report_status":
            lineage.report_status,

        "impression":
            lineage.impression,

        "lineage_status":
            "MATCHED",
    }


def find_existing_workflow(
    *,
    accession_number: str,
    study_instance_uid: str,
) -> dict[str, str] | None:
    """
    Look for a canonical workflow using either of the two
    primary imaging identities.

    In this controlled lab, accession number and DICOM
    Study Instance UID are each expected to identify one
    canonical workflow.
    """

    sql = f"""
SELECT
    radiology_workflow_id,
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code,
    procedure_text,
    study_instance_uid,
    modality,
    oru_message_control_id,
    report_status,
    impression,
    lineage_status
FROM audit.radiology_workflows
WHERE accession_number =
      {sql_literal(accession_number)}
   OR study_instance_uid =
      {sql_literal(study_instance_uid)}
ORDER BY radiology_workflow_id;
""".strip()

    output = run_interop_db_sql(
        sql
    )

    if not output:
        return None

    rows = output.splitlines()

    if len(rows) != 1:
        raise RuntimeError(
            "Radiology workflow identity resolved to "
            f"{len(rows)} canonical rows; expected 1."
        )

    fields = rows[0].split("|")

    if len(fields) != 12:
        raise RuntimeError(
            "Unexpected radiology workflow query result: "
            f"{rows[0]!r}"
        )

    return {
        "radiology_workflow_id": fields[0],
        "patient_identifier": fields[1],
        "placer_order_number": fields[2],
        "accession_number": fields[3],
        "procedure_code": fields[4],
        "procedure_text": fields[5],
        "study_instance_uid": fields[6],
        "modality": fields[7],
        "oru_message_control_id": fields[8],
        "report_status": fields[9],
        "impression": fields[10],
        "lineage_status": fields[11],
    }


def assert_existing_matches_expected(
    existing: dict[str, str],
    expected: dict[str, str],
) -> None:
    """
    Reject reuse of an existing accession or Study UID when
    the associated clinical workflow data has changed.
    """

    fields_to_compare = [
        "patient_identifier",
        "placer_order_number",
        "accession_number",
        "procedure_code",
        "procedure_text",
        "study_instance_uid",
        "modality",
        "oru_message_control_id",
        "report_status",
        "impression",
        "lineage_status",
    ]

    mismatches: list[str] = []

    for field in fields_to_compare:
        if existing[field] != expected[field]:
            mismatches.append(
                f"{field}: "
                f"{existing[field]!r} != "
                f"{expected[field]!r}"
            )

    if mismatches:
        details = "; ".join(
            mismatches
        )

        raise RuntimeError(
            "Conflicting radiology workflow identity reuse "
            f"detected: {details}"
        )


def insert_workflow(
    expected: dict[str, str],
) -> int:
    sql = f"""
INSERT INTO audit.radiology_workflows (
    patient_identifier,
    placer_order_number,
    accession_number,
    procedure_code,
    procedure_text,
    study_instance_uid,
    modality,
    oru_message_control_id,
    report_status,
    impression,
    lineage_status
)
VALUES (
    {sql_literal(expected["patient_identifier"])},
    {sql_literal(expected["placer_order_number"])},
    {sql_literal(expected["accession_number"])},
    {sql_literal(expected["procedure_code"])},
    {sql_literal(expected["procedure_text"])},
    {sql_literal(expected["study_instance_uid"])},
    {sql_literal(expected["modality"])},
    {sql_literal(expected["oru_message_control_id"])},
    {sql_literal(expected["report_status"])},
    {sql_literal(expected["impression"])},
    {sql_literal(expected["lineage_status"])}
)
RETURNING radiology_workflow_id;
""".strip()

    output = run_interop_db_sql(
        sql
    )

    if not output:
        raise RuntimeError(
            "Radiology workflow persistence returned "
            "no workflow ID."
        )

    first_line = output.splitlines()[0].strip()

    return int(first_line)  


def persist_radiology_lineage(
    orm_path: Path,
    dicom_path: Path,
    oru_path: Path,
) -> int:
    """
    Validate and persist one canonical radiology workflow.

    Processing order:

        parse
        -> validate
        -> establish identity
        -> detect replay/conflict
        -> persist

    Returns the canonical radiology_workflow_id.
    """

    orm = analyze_orm(
        orm_path
    )

    dicom = pydicom.dcmread(
        dicom_path,
        stop_before_pixels=True,
    )

    oru = analyze_radiology_oru(
        oru_path
    )

    lineage = validate_full_radiology_lineage(
        orm,
        dicom,
        oru,
    )

    expected = build_expected_record(
        lineage,
        oru,
    )

    existing = find_existing_workflow(
        accession_number=
            lineage.accession_number,
        study_instance_uid=
            lineage.study_instance_uid,
    )

    if existing is not None:
        assert_existing_matches_expected(
            existing,
            expected,
        )

        return int(
            existing[
                "radiology_workflow_id"
            ]
        )

    return insert_workflow(
        expected
    )


def delete_radiology_workflow(
    radiology_workflow_id: int,
) -> None:
    """
    Test/support helper for removing synthetic workflow rows.
    """

    sql = f"""
DELETE FROM audit.radiology_workflows
WHERE radiology_workflow_id =
      {int(radiology_workflow_id)};
""".strip()

    run_interop_db_sql(
        sql
    )