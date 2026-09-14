import json

import pytest

from scripts.radiology import mwl_projection


def projection_row() -> dict:
    return {
        "mwl_item_id": 12,
        "orm_order_id": 258,
        "patient_identifier": "LAB000001",
        "patient_family_name": "Testpatient",
        "patient_given_name": "Avery",
        "patient_date_of_birth": "19800115",
        "patient_administrative_sex": "M",
        "accession_number": "RADF3234B83A1",
        "requested_procedure_id":
            "RADORDF3234B83A1",
        "procedure_code": "XRCH2",
        "procedure_description":
            "Chest X-ray 2 Views",
        "modality": "DX",
        "scheduled_station_ae_title":
            "XRAY_MODALITY",
        "scheduled_start_date": "20260824",
        "scheduled_start_time": "193000",
        "schedule_source": "ORDER_DATETIME",
        "scheduled_procedure_step_id":
            "RADF3234B83A1",
        "projection_status": "IN_PROGRESS",
        "projection_attempt_count": 1,
    }


def full_worklist(
    row: dict,
    study_uid: str,
    *,
    worklist_id: str = "orthanc-mwl-12",
) -> dict:
    return {
        "ID": worklist_id,
        "Tags": {
            "0010,0020": {
                "Value": row[
                    "patient_identifier"
                ],
            },
            "0010,0010": {
                "Value": (
                    f"{row['patient_family_name']}^"
                    f"{row['patient_given_name']}"
                ),
            },
            "0010,0030": {
                "Value": row[
                    "patient_date_of_birth"
                ],
            },
            "0010,0040": {
                "Value": row[
                    "patient_administrative_sex"
                ],
            },
            "0008,0050": {
                "Value": row[
                    "accession_number"
                ],
            },
            "0020,000d": {
                "Value": study_uid,
            },
            "0040,1001": {
                "Value": row[
                    "requested_procedure_id"
                ],
            },
            "0032,1060": {
                "Value": row[
                    "procedure_description"
                ],
            },
            "0040,0100": {
                "Value": [
                    {
                        "0008,0060": {
                            "Value": row[
                                "modality"
                            ],
                        },
                        "0040,0001": {
                            "Value": row[
                                "scheduled_station_ae_title"
                            ],
                        },
                        "0040,0002": {
                            "Value": row[
                                "scheduled_start_date"
                            ],
                        },
                        "0040,0003": {
                            "Value": row[
                                "scheduled_start_time"
                            ],
                        },
                        "0040,0009": {
                            "Value": row[
                                "scheduled_procedure_step_id"
                            ],
                        },
                        "0040,0007": {
                            "Value": row[
                                "procedure_description"
                            ],
                        },
                    }
                ],
            },
        },
    }


def test_deterministic_study_uid_is_stable_and_bounded():
    row = projection_row()

    first = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    second = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    changed = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"] + 1,
            row["accession_number"],
        )
    )

    assert first == second
    assert first != changed
    assert first.startswith("2.25.")
    assert len(first) <= 64

    numeric_components = first.split(".")
    assert numeric_components[0] == "2"
    assert numeric_components[1] == "25"
    assert numeric_components[2].isdigit()


def test_payload_preserves_projection_identity():
    row = projection_row()

    study_uid = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    payload = (
        mwl_projection.build_worklist_payload(
            row,
            study_uid,
        )
    )

    tags = payload["Tags"]
    step = tags[
        "ScheduledProcedureStepSequence"
    ][0]

    assert tags["PatientID"] == "LAB000001"

    assert (
        tags["PatientName"]
        == "Testpatient^Avery"
    )

    assert (
        tags["PatientBirthDate"]
        == "19800115"
    )

    assert tags["PatientSex"] == "M"

    assert (
        tags["AccessionNumber"]
        == "RADF3234B83A1"
    )

    assert tags["StudyInstanceUID"] == study_uid

    assert (
        tags["RequestedProcedureID"]
        == "RADORDF3234B83A1"
    )

    assert (
        tags["RequestedProcedureDescription"]
        == "Chest X-ray 2 Views"
    )

    assert step == {
        "ScheduledStationAETitle":
            "XRAY_MODALITY",
        "ScheduledProcedureStepStartDate":
            "20260824",
        "ScheduledProcedureStepStartTime":
            "193000",
        "Modality": "DX",
        "ScheduledProcedureStepID":
            "RADF3234B83A1",
        "ScheduledProcedureStepDescription":
            "Chest X-ray 2 Views",
    }


def test_reconciliation_returns_none_when_absent():
    row = projection_row()

    study_uid = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    assert (
        mwl_projection.find_existing_worklist(
            row,
            study_uid,
            [],
        )
        is None
    )


def test_reconciliation_returns_exact_worklist_id():
    row = projection_row()

    study_uid = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    worklist = full_worklist(
        row,
        study_uid,
    )

    assert (
        mwl_projection.find_existing_worklist(
            row,
            study_uid,
            [worklist],
        )
        == "orthanc-mwl-12"
    )


def test_reconciliation_rejects_identity_mismatch():
    row = projection_row()

    study_uid = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    worklist = full_worklist(
        row,
        study_uid,
    )

    worklist["Tags"]["0010,0020"][
        "Value"
    ] = "WRONGPATIENT"

    with pytest.raises(
        RuntimeError,
        match=(
            "Orthanc worklist identity mismatch"
        ),
    ):
        mwl_projection.find_existing_worklist(
            row,
            study_uid,
            [worklist],
        )


def test_reconciliation_rejects_duplicate_accession():
    row = projection_row()

    study_uid = (
        mwl_projection.deterministic_study_uid(
            row["mwl_item_id"],
            row["accession_number"],
        )
    )

    first = full_worklist(
        row,
        study_uid,
        worklist_id="first",
    )

    second = full_worklist(
        row,
        study_uid,
        worklist_id="second",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Multiple Orthanc worklists match"
        ),
    ):
        mwl_projection.find_existing_worklist(
            row,
            study_uid,
            [first, second],
        )


def test_claim_uses_transactional_concurrency_guard(
    monkeypatch,
):
    row = projection_row()
    captured = {}

    def fake_run_psql(
        sql: str,
        *,
        container: str,
    ) -> str:
        captured["sql"] = sql
        captured["container"] = container
        return json.dumps(row)

    monkeypatch.setattr(
        mwl_projection,
        "run_psql",
        fake_run_psql,
    )

    claimed = mwl_projection.claim_projection(
        12,
        stale_minutes=5,
        container="test-db",
    )

    assert claimed == row
    assert captured["container"] == "test-db"

    normalized_sql = " ".join(
        captured["sql"].split()
    )

    assert "BEGIN;" in normalized_sql
    assert "FOR UPDATE SKIP LOCKED" in normalized_sql
    assert "projection_status = 'IN_PROGRESS'" in normalized_sql
    assert "projection_attempt_count + 1" in normalized_sql
    assert "claimed_at = CURRENT_TIMESTAMP" in normalized_sql
    assert "INTERVAL '5 minutes'" in normalized_sql
    assert "COMMIT;" in normalized_sql