from __future__ import annotations

from typing import Any

from pydicom.dataset import Dataset


BOUNDARY_ORDER = (
    "orm_order",
    "mwl_projection",
    "pacs_study",
    "final_oru",
)


def _mapping_value(
    source: dict[str, Any],
    field: str,
) -> Any:
    return source.get(field)


def _dicom_value(
    source: Dataset,
    field: str,
) -> str | None:
    value = getattr(source, field, None)

    if value is None:
        return None

    return str(value)


def _add_check(
    checks: list[dict[str, Any]],
    boundary: str,
    field: str,
    expected: Any,
    actual: Any,
    *,
    passed: bool | None = None,
) -> None:
    if passed is None:
        passed = actual == expected

    checks.append(
        {
            "field": field,
            "boundary": boundary,
            "expected": expected,
            "actual": actual,
            "status": (
                "PASS" if passed else "FAIL"
            ),
        }
    )


def _add_presence_check(
    checks: list[dict[str, Any]],
    boundary: str,
    field: str,
    actual: Any,
) -> None:
    _add_check(
        checks,
        boundary,
        field,
        "present",
        actual,
        passed=actual is not None and actual != "",
    )


def _boundary_status(
    checks: list[dict[str, Any]],
    boundary: str,
) -> str:
    boundary_checks = [
        check
        for check in checks
        if check["boundary"] == boundary
    ]

    if any(
        check["status"] == "FAIL"
        for check in boundary_checks
    ):
        return "FAIL"

    return "PASS"


def reconcile_accession_workflow(
    orm: dict[str, Any] | None,
    mwl: dict[str, Any] | None,
    dicom: Dataset | None,
    oru: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reconcile one ORM -> MWL -> PACS -> ORU workflow."""

    checks: list[dict[str, Any]] = []
    boundaries: dict[str, str] = {}

    if orm is None:
        boundaries["orm_order"] = "INCOMPLETE"
    else:
        for field in (
            "patient_id",
            "orc_placer_order_number",
            "accession_number",
            "procedure_code",
            "procedure_text",
        ):
            _add_presence_check(
                checks,
                "orm_order",
                field,
                _mapping_value(orm, field),
            )

        boundaries["orm_order"] = (
            _boundary_status(checks, "orm_order")
        )

    if mwl is None:
        boundaries["mwl_projection"] = "INCOMPLETE"
    elif orm is None:
        boundaries["mwl_projection"] = "INCOMPLETE"
    else:
        mwl_expectations = (
            (
                "patient_identifier",
                orm.get("patient_id"),
            ),
            (
                "requested_procedure_id",
                orm.get("orc_placer_order_number"),
            ),
            (
                "accession_number",
                orm.get("accession_number"),
            ),
            (
                "procedure_code",
                orm.get("procedure_code"),
            ),
            (
                "procedure_description",
                orm.get("procedure_text"),
            ),
            ("projection_status", "PUBLISHED"),
        )

        for field, expected in mwl_expectations:
            _add_check(
                checks,
                "mwl_projection",
                field,
                expected,
                mwl.get(field),
            )

        for field in (
            "study_instance_uid",
            "orthanc_worklist_id",
        ):
            _add_presence_check(
                checks,
                "mwl_projection",
                field,
                mwl.get(field),
            )

        boundaries["mwl_projection"] = (
            _boundary_status(
                checks,
                "mwl_projection",
            )
        )

    if dicom is None:
        boundaries["pacs_study"] = "INCOMPLETE"
    elif orm is None or mwl is None:
        boundaries["pacs_study"] = "INCOMPLETE"
    else:
        pacs_expectations = (
            (
                "patient_id",
                orm.get("patient_id"),
                _dicom_value(dicom, "PatientID"),
            ),
            (
                "accession_number",
                orm.get("accession_number"),
                _dicom_value(dicom, "AccessionNumber"),
            ),
            (
                "procedure_text",
                orm.get("procedure_text"),
                _dicom_value(dicom, "StudyDescription"),
            ),
            (
                "study_instance_uid",
                mwl.get("study_instance_uid"),
                _dicom_value(dicom, "StudyInstanceUID"),
            ),
            (
                "modality",
                mwl.get("modality"),
                _dicom_value(dicom, "Modality"),
            ),
        )

        for field, expected, actual in pacs_expectations:
            _add_check(
                checks,
                "pacs_study",
                field,
                expected,
                actual,
            )

        boundaries["pacs_study"] = (
            _boundary_status(checks, "pacs_study")
        )

    if oru is None:
        boundaries["final_oru"] = "INCOMPLETE"
    elif orm is None:
        boundaries["final_oru"] = "INCOMPLETE"
    else:
        oru_expectations = (
            ("patient_id", orm.get("patient_id")),
            (
                "placer_order_number",
                orm.get("orc_placer_order_number"),
            ),
            (
                "filler_order_number",
                orm.get("accession_number"),
            ),
            ("service_code", orm.get("procedure_code")),
            ("service_text", orm.get("procedure_text")),
            ("obr_result_status", "F"),
            ("obx_result_status", "F"),
            ("observation_code", "IMPRESSION"),
        )

        for field, expected in oru_expectations:
            _add_check(
                checks,
                "final_oru",
                field,
                expected,
                oru.get(field),
            )

        _add_presence_check(
            checks,
            "final_oru",
            "observation_value",
            oru.get("observation_value"),
        )

        boundaries["final_oru"] = (
            _boundary_status(checks, "final_oru")
        )

    boundary_states = [
        boundaries[name]
        for name in BOUNDARY_ORDER
    ]

    if "INCOMPLETE" in boundary_states:
        status = "INCOMPLETE"
    elif "FAIL" in boundary_states:
        status = "QUARANTINE"
    else:
        status = "PASS"

    workflow = {
        "patient_id": (
            None if orm is None
            else orm.get("patient_id")
        ),
        "placer_order_number": (
            None if orm is None
            else orm.get("orc_placer_order_number")
        ),
        "accession_number": (
            None if orm is None
            else orm.get("accession_number")
        ),
        "study_instance_uid": (
            None if mwl is None
            else mwl.get("study_instance_uid")
        ),
    }

    return {
        "status": status,
        "workflow": workflow,
        "boundaries": boundaries,
        "checks": checks,
    }
