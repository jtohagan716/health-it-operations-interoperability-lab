import argparse
import json
import subprocess
import sys
import uuid
from urllib.request import Request, urlopen


DEFAULT_DB_CONTAINER = (
    "health-it-mirth-lab-interop-db-1"
)

DEFAULT_ORTHANC_URL = (
    "http://127.0.0.1:8042"
)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_psql(
    sql: str,
    *,
    container: str = DEFAULT_DB_CONTAINER,
) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "sh",
            "-lc",
            (
                "exec psql "
                "-v ON_ERROR_STOP=1 "
                '-U "$POSTGRES_USER" '
                '-d "$POSTGRES_DB" '
                "-A -t"
            ),
        ],
        input=sql,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Interop database command failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result.stdout.strip()


def orthanc_request(
    method: str,
    path: str,
    *,
    base_url: str = DEFAULT_ORTHANC_URL,
    payload: dict | None = None,
) -> object:
    body = None
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode(
            "utf-8"
        )
        headers["Content-Type"] = (
            "application/json"
        )

    request = Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    with urlopen(
        request,
        timeout=10,
    ) as response:
        response_body = response.read()

    if not response_body:
        return None

    return json.loads(
        response_body.decode("utf-8")
    )


def deterministic_study_uid(
    mwl_item_id: int,
    accession_number: str,
) -> str:
    identity = (
        "urn:health-it-interop-lab:"
        f"mwl:{mwl_item_id}:"
        f"{accession_number}"
    )

    value = uuid.uuid5(
        uuid.NAMESPACE_URL,
        identity,
    )

    study_uid = "2.25." + str(value.int)

    if len(study_uid) > 64:
        raise RuntimeError(
            "Deterministic Study Instance UID "
            "exceeds 64 characters."
        )

    return study_uid


def claim_projection(
    mwl_item_id: int,
    *,
    stale_minutes: int,
    container: str,
) -> dict:
    if stale_minutes < 1:
        raise ValueError(
            "Stale claim interval must be at "
            "least one minute."
        )

    output = run_psql(
        f"""
BEGIN;

WITH candidate AS (
    SELECT mwl_item_id
    FROM audit.modality_worklist_items
    WHERE mwl_item_id = {int(mwl_item_id)}
      AND (
          projection_status IN (
              'PENDING',
              'FAILED'
          )
          OR (
              projection_status = 'IN_PROGRESS'
              AND claimed_at <
                  CURRENT_TIMESTAMP
                  - INTERVAL
                    '{int(stale_minutes)} minutes'
          )
      )
    FOR UPDATE SKIP LOCKED
), claimed AS (
    UPDATE audit.modality_worklist_items m
    SET projection_status = 'IN_PROGRESS',
        projection_attempt_count =
            projection_attempt_count + 1,
        claimed_at = CURRENT_TIMESTAMP,
        last_error = NULL,
        updated_at = CURRENT_TIMESTAMP
    FROM candidate c
    WHERE m.mwl_item_id = c.mwl_item_id
    RETURNING m.*
)
SELECT row_to_json(c)
FROM claimed c;

COMMIT;
""".strip(),
        container=container,
    )

    rows = [
        line
        for line in output.splitlines()
        if line.startswith("{")
    ]

    if not rows:
        raise RuntimeError(
            "No eligible MWL projection is "
            "available for item "
            f"{mwl_item_id}."
        )

    return json.loads(rows[-1])


def build_worklist_payload(
    row: dict,
    study_instance_uid: str,
) -> dict:
    patient_name = (
        f"{row['patient_family_name']}^"
        f"{row['patient_given_name']}"
    )

    return {
        "Tags": {
            "PatientID": (
                row["patient_identifier"]
            ),
            "PatientName": patient_name,
            "PatientBirthDate": (
                row["patient_date_of_birth"]
            ),
            "PatientSex": (
                row[
                    "patient_administrative_sex"
                ]
            ),
            "AccessionNumber": (
                row["accession_number"]
            ),
            "StudyInstanceUID": (
                study_instance_uid
            ),
            "RequestedProcedureID": (
                row["requested_procedure_id"]
            ),
            "RequestedProcedureDescription": (
                row["procedure_description"]
            ),
            "ScheduledProcedureStepSequence": [
                {
                    "ScheduledStationAETitle": (
                        row[
                            "scheduled_station_ae_title"
                        ]
                    ),
                    "ScheduledProcedureStepStartDate": (
                        row[
                            "scheduled_start_date"
                        ]
                    ),
                    "ScheduledProcedureStepStartTime": (
                        row[
                            "scheduled_start_time"
                        ]
                    ),
                    "Modality": (
                        row["modality"]
                    ),
                    "ScheduledProcedureStepID": (
                        row[
                            "scheduled_procedure_step_id"
                        ]
                    ),
                    "ScheduledProcedureStepDescription": (
                        row[
                            "procedure_description"
                        ]
                    ),
                }
            ],
        }
    }


def tag_value(
    tags: dict,
    tag: str,
) -> str:
    item = tags.get(tag, {})

    value = item.get("Value", "")

    if value is None:
        return ""

    return str(value)


def expected_worklist_identity(
    row: dict,
    study_instance_uid: str,
) -> dict[str, str]:
    return {
        "PatientID": str(
            row["patient_identifier"]
        ),
        "PatientName": (
            f"{row['patient_family_name']}^"
            f"{row['patient_given_name']}"
        ),
        "PatientBirthDate": str(
            row["patient_date_of_birth"]
        ),
        "PatientSex": str(
            row[
                "patient_administrative_sex"
            ]
        ),
        "AccessionNumber": str(
            row["accession_number"]
        ),
        "StudyInstanceUID":
            study_instance_uid,
        "RequestedProcedureID": str(
            row["requested_procedure_id"]
        ),
        "RequestedProcedureDescription": str(
            row["procedure_description"]
        ),
        "Modality": str(
            row["modality"]
        ),
        "ScheduledStationAETitle": str(
            row[
                "scheduled_station_ae_title"
            ]
        ),
        "ScheduledProcedureStepStartDate": str(
            row["scheduled_start_date"]
        ),
        "ScheduledProcedureStepStartTime": str(
            row["scheduled_start_time"]
        ),
        "ScheduledProcedureStepID": str(
            row[
                "scheduled_procedure_step_id"
            ]
        ),
        "ScheduledProcedureStepDescription": str(
            row["procedure_description"]
        ),
    }


def observed_worklist_identity(
    worklist: dict,
) -> dict[str, str]:
    tags = worklist.get("Tags", {})

    sequence = (
        tags
        .get("0040,0100", {})
        .get("Value", [])
    )

    if (
        not isinstance(sequence, list)
        or len(sequence) != 1
        or not isinstance(sequence[0], dict)
    ):
        raise RuntimeError(
            "Orthanc worklist identity mismatch: "
            "expected exactly one scheduled "
            "procedure step."
        )

    step = sequence[0]

    return {
        "PatientID":
            tag_value(tags, "0010,0020"),
        "PatientName":
            tag_value(tags, "0010,0010"),
        "PatientBirthDate":
            tag_value(tags, "0010,0030"),
        "PatientSex":
            tag_value(tags, "0010,0040"),
        "AccessionNumber":
            tag_value(tags, "0008,0050"),
        "StudyInstanceUID":
            tag_value(tags, "0020,000d"),
        "RequestedProcedureID":
            tag_value(tags, "0040,1001"),
        "RequestedProcedureDescription":
            tag_value(tags, "0032,1060"),
        "Modality":
            tag_value(step, "0008,0060"),
        "ScheduledStationAETitle":
            tag_value(step, "0040,0001"),
        "ScheduledProcedureStepStartDate":
            tag_value(step, "0040,0002"),
        "ScheduledProcedureStepStartTime":
            tag_value(step, "0040,0003"),
        "ScheduledProcedureStepID":
            tag_value(step, "0040,0009"),
        "ScheduledProcedureStepDescription":
            tag_value(step, "0040,0007"),
    }


def find_existing_worklist(
    row: dict,
    study_instance_uid: str,
    worklists: list[dict],
) -> str | None:
    accession_number = str(
        row["accession_number"]
    )

    matches = []

    for worklist in worklists:
        tags = worklist.get("Tags", {})

        if (
            tag_value(tags, "0008,0050")
            == accession_number
        ):
            matches.append(worklist)

    if len(matches) > 1:
        raise RuntimeError(
            "Multiple Orthanc worklists match "
            f"accession {accession_number}."
        )

    if not matches:
        return None

    worklist = matches[0]

    expected = expected_worklist_identity(
        row,
        study_instance_uid,
    )

    observed = observed_worklist_identity(
        worklist
    )

    if observed != expected:
        mismatches = [
            field
            for field in expected
            if observed.get(field)
            != expected[field]
        ]

        raise RuntimeError(
            "Orthanc worklist identity mismatch "
            f"for accession {accession_number}: "
            + ", ".join(mismatches)
        )

    orthanc_worklist_id = worklist.get(
        "ID"
    )

    if not orthanc_worklist_id:
        raise RuntimeError(
            "Matching Orthanc worklist has no ID."
        )

    return str(orthanc_worklist_id)


def list_worklists(
    *,
    base_url: str,
) -> list[dict]:
    result = orthanc_request(
        "GET",
        "/worklists/?format=Full",
        base_url=base_url,
    )

    if not isinstance(result, list):
        raise RuntimeError(
            "Orthanc worklist collection returned "
            "an invalid response."
        )

    return result


def mark_published(
    row: dict,
    study_instance_uid: str,
    orthanc_worklist_id: str,
    *,
    container: str,
) -> None:
    output = run_psql(
        f"""
WITH updated AS (
    UPDATE audit.modality_worklist_items
    SET projection_status = 'PUBLISHED',
        study_instance_uid =
            {sql_literal(study_instance_uid)},
        orthanc_worklist_id =
            {sql_literal(orthanc_worklist_id)},
        published_at = CURRENT_TIMESTAMP,
        last_error = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE mwl_item_id =
          {int(row["mwl_item_id"])}
      AND projection_status = 'IN_PROGRESS'
    RETURNING mwl_item_id
)
SELECT COUNT(*)
FROM updated;
""".strip(),
        container=container,
    )

    if output.splitlines()[-1:] != ["1"]:
        raise RuntimeError(
            "MWL projection publication state "
            "was not updated exactly once."
        )


def mark_failed(
    row: dict,
    error: str,
    *,
    container: str,
) -> None:
    output = run_psql(
        f"""
WITH updated AS (
    UPDATE audit.modality_worklist_items
    SET projection_status = 'FAILED',
        last_error = {sql_literal(error)},
        updated_at = CURRENT_TIMESTAMP
    WHERE mwl_item_id =
          {int(row["mwl_item_id"])}
      AND projection_status = 'IN_PROGRESS'
    RETURNING mwl_item_id
)
SELECT COUNT(*)
FROM updated;
""".strip(),
        container=container,
    )

    if output.splitlines()[-1:] != ["1"]:
        raise RuntimeError(
            "MWL projection failure state "
            "was not updated exactly once."
        )


def reconcile_after_failure(
    row: dict,
    study_instance_uid: str,
    *,
    base_url: str,
) -> str | None:
    worklists = list_worklists(
        base_url=base_url
    )

    return find_existing_worklist(
        row,
        study_instance_uid,
        worklists,
    )


def publish_projection(
    mwl_item_id: int,
    *,
    stale_minutes: int,
    container: str,
    base_url: str,
) -> dict:
    row = claim_projection(
        mwl_item_id,
        stale_minutes=stale_minutes,
        container=container,
    )

    study_instance_uid = (
        deterministic_study_uid(
            int(row["mwl_item_id"]),
            str(row["accession_number"]),
        )
    )

    try:
        existing_id = find_existing_worklist(
            row,
            study_instance_uid,
            list_worklists(
                base_url=base_url
            ),
        )

        publication_mode = "RECONCILED"

        if existing_id is None:
            payload = build_worklist_payload(
                row,
                study_instance_uid,
            )

            created = orthanc_request(
                "POST",
                "/worklists/create",
                base_url=base_url,
                payload=payload,
            )

            if not isinstance(created, dict):
                raise RuntimeError(
                    "Orthanc worklist creation "
                    "returned an invalid response."
                )

            created_id = created.get("ID")

            if not created_id:
                raise RuntimeError(
                    "Orthanc worklist creation "
                    "returned no ID."
                )

            existing_id = (
                find_existing_worklist(
                    row,
                    study_instance_uid,
                    list_worklists(
                        base_url=base_url
                    ),
                )
            )

            if existing_id is None:
                raise RuntimeError(
                    "Created Orthanc worklist "
                    "could not be reconciled."
                )

            if existing_id != str(created_id):
                raise RuntimeError(
                    "Created Orthanc worklist ID "
                    "does not match reconciliation."
                )

            publication_mode = "CREATED"

        mark_published(
            row,
            study_instance_uid,
            existing_id,
            container=container,
        )

        return {
            "status": "PUBLISHED",
            "publication_mode":
                publication_mode,
            "mwl_item_id":
                int(row["mwl_item_id"]),
            "orm_order_id":
                int(row["orm_order_id"]),
            "accession_number":
                row["accession_number"],
            "study_instance_uid":
                study_instance_uid,
            "orthanc_worklist_id":
                existing_id,
            "attempt_count":
                int(
                    row[
                        "projection_attempt_count"
                    ]
                ),
        }

    except Exception as initial_error:
        try:
            recovered_id = (
                reconcile_after_failure(
                    row,
                    study_instance_uid,
                    base_url=base_url,
                )
            )
        except Exception as reconciliation_error:
            combined_error = (
                f"{initial_error}; "
                "reconciliation failed: "
                f"{reconciliation_error}"
            )

            mark_failed(
                row,
                combined_error,
                container=container,
            )

            raise RuntimeError(
                combined_error
            ) from initial_error

        if recovered_id is not None:
            mark_published(
                row,
                study_instance_uid,
                recovered_id,
                container=container,
            )

            return {
                "status": "PUBLISHED",
                "publication_mode":
                    "RECOVERED",
                "mwl_item_id":
                    int(row["mwl_item_id"]),
                "orm_order_id":
                    int(row["orm_order_id"]),
                "accession_number":
                    row["accession_number"],
                "study_instance_uid":
                    study_instance_uid,
                "orthanc_worklist_id":
                    recovered_id,
                "attempt_count":
                    int(
                        row[
                            "projection_attempt_count"
                        ]
                    ),
            }

        mark_failed(
            row,
            str(initial_error),
            container=container,
        )

        raise RuntimeError(
            str(initial_error)
        ) from initial_error


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Publish one durable ORM-derived "
            "DICOM Modality Worklist projection "
            "to Orthanc."
        )
    )

    command.add_argument(
        "--mwl-item-id",
        type=int,
        required=True,
    )

    command.add_argument(
        "--confirm-mwl-item-id",
        type=int,
        required=True,
    )

    command.add_argument(
        "--stale-minutes",
        type=int,
        default=5,
    )

    command.add_argument(
        "--db-container",
        default=DEFAULT_DB_CONTAINER,
    )

    command.add_argument(
        "--orthanc-url",
        default=DEFAULT_ORTHANC_URL,
    )

    return command


def main() -> int:
    args = parser().parse_args()

    if (
        args.confirm_mwl_item_id
        != args.mwl_item_id
    ):
        print(
            "MWL projection confirmation does not match "
            f"item {args.mwl_item_id}."
        )
        return 1

    try:
        result = publish_projection(
            args.mwl_item_id,
            stale_minutes=args.stale_minutes,
            container=args.db_container,
            base_url=args.orthanc_url,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            "MWL PROJECTION PUBLICATION: "
            f"FAIL - {exc}"
        )
        return 1

    print(
        json.dumps(
            result,
            indent=2,
        )
    )
    print(
        "MWL PROJECTION PUBLICATION: PASS"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())