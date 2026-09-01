import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.hl7.openemr_oru_ingest import (
    OpenEmrTarget,
    execute_openemr_scenario,
)


DEFAULT_DB_CONTAINER = "health-it-mirth-lab-interop-db-1"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_psql(sql: str, *, container: str = DEFAULT_DB_CONTAINER) -> str:
    result = subprocess.run(
        [
            "docker", "exec", "-i", container, "sh", "-lc",
            'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" '
            '-d "$POSTGRES_DB" -A -t',
        ],
        input=sql,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Interop database command failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def register_target(args: argparse.Namespace) -> None:
    if args.confirm_order_id != args.order_id:
        raise ValueError(
            "Registration requires --confirm-order-id matching "
            f"Order ID {args.order_id}."
        )
    values = {
        "placer": sql_literal(args.placer_order),
        "identifier": sql_literal(args.patient_identifier),
        "family": sql_literal(args.patient_family_name),
        "given": sql_literal(args.patient_given_name),
        "dob": sql_literal(args.patient_date_of_birth),
        "sex": sql_literal(args.patient_sex),
    }
    run_psql(
        f"""
        INSERT INTO audit.openemr_oru_targets (
            placer_order_number, openemr_order_id, openemr_patient_id,
            openemr_encounter_id, openemr_lab_id, patient_identifier,
            patient_family_name, patient_given_name, patient_date_of_birth,
            patient_administrative_sex
        ) VALUES (
            {values['placer']}, {args.order_id}, {args.patient_id},
            {args.encounter_id}, {args.lab_id}, {values['identifier']},
            {values['family']}, {values['given']}, {values['dob']}, {values['sex']}
        )
        ON CONFLICT (placer_order_number) DO UPDATE SET
            openemr_order_id = EXCLUDED.openemr_order_id,
            openemr_patient_id = EXCLUDED.openemr_patient_id,
            openemr_encounter_id = EXCLUDED.openemr_encounter_id,
            openemr_lab_id = EXCLUDED.openemr_lab_id,
            patient_identifier = EXCLUDED.patient_identifier,
            patient_family_name = EXCLUDED.patient_family_name,
            patient_given_name = EXCLUDED.patient_given_name,
            patient_date_of_birth = EXCLUDED.patient_date_of_birth,
            patient_administrative_sex = EXCLUDED.patient_administrative_sex,
            active = TRUE;
        """,
        container=args.db_container,
    )


def claim_delivery(args: argparse.Namespace) -> dict:
    selector = (
        f"d.delivery_id = {args.delivery_id}"
        if args.delivery_id is not None
        else "d.delivery_status IN ('PENDING', 'FAILED')"
    )
    output = run_psql(
        f"""
        BEGIN;
        WITH candidate AS (
            SELECT d.delivery_id
              FROM audit.openemr_oru_deliveries d
              JOIN audit.oru_messages m USING (oru_message_id)
              JOIN audit.openemr_oru_targets t
                ON t.placer_order_number = m.placer_order_number
               AND t.active = TRUE
             WHERE {selector}
               AND EXISTS (
                    SELECT 1
                      FROM audit.oru_observations o
                     WHERE o.oru_message_id = d.oru_message_id
               )
             ORDER BY d.created_at, d.delivery_id
             FOR UPDATE SKIP LOCKED
             LIMIT 1
        ), claimed AS (
            UPDATE audit.openemr_oru_deliveries d
               SET delivery_status = 'IN_PROGRESS',
                   attempt_count = attempt_count + 1,
                   claimed_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP,
                   last_error = NULL
              FROM candidate c
             WHERE d.delivery_id = c.delivery_id
         RETURNING d.*
        )
        SELECT row_to_json(payload)
          FROM (
            SELECT c.delivery_id, c.oru_message_id,
                   t.openemr_order_id AS order_id,
                   t.openemr_patient_id AS patient_id,
                   t.openemr_encounter_id AS encounter_id,
                   t.openemr_lab_id AS lab_id,
                   t.patient_identifier, t.patient_family_name,
                   t.patient_given_name, t.patient_date_of_birth,
                   t.patient_administrative_sex,
                   m.message_control_id, m.sending_application,
                   m.sending_facility, m.placer_order_number,
                   m.filler_order_number, m.service_code,
                   m.service_text, m.obr_result_status,
                   m.received_at,
                   o.value_type, o.observation_code,
                   o.observation_text, o.observation_value,
                   o.units, o.reference_range, o.abnormal_flag,
                   o.result_status
              FROM claimed c
              JOIN audit.oru_messages m USING (oru_message_id)
              JOIN audit.openemr_oru_targets t
                ON t.placer_order_number = m.placer_order_number
               AND t.active = TRUE
              JOIN LATERAL (
                    SELECT * FROM audit.oru_observations
                     WHERE oru_message_id = m.oru_message_id
                     ORDER BY oru_observation_id LIMIT 1
              ) o ON TRUE
          ) payload;
        COMMIT;
        """,
        container=args.db_container,
    )
    rows = [line for line in output.splitlines() if line.startswith("{")]
    if not rows:
        raise RuntimeError("No eligible OpenEMR delivery is available.")
    return json.loads(rows[-1])


def scenario_from_delivery(row: dict) -> dict:
    timestamp = str(row["received_at"]).replace("-", "").replace(":", "")
    timestamp = timestamp.replace("T", "").replace(" ", "")[:14]
    return {
        "scenario_id": f"mirth-oru-{row['oru_message_id']}",
        "message": {
            "timestamp": timestamp,
            "control_id": row["message_control_id"],
            "sending_application": row["sending_application"],
            "sending_facility": row["sending_facility"],
        },
        "patient": {
            "identifier": row["patient_identifier"],
            "family_name": row["patient_family_name"],
            "given_name": row["patient_given_name"],
            "date_of_birth": row["patient_date_of_birth"],
            "administrative_sex": row["patient_administrative_sex"],
        },
        "order": {
            "placer_number": row["placer_order_number"],
            "filler_number": row["filler_order_number"],
            "service_code": row["service_code"],
            "service_display": row["service_text"] or row["service_code"],
            "observation_timestamp": timestamp,
            "result_status": row["obr_result_status"] or "F",
        },
        "observation": {
            "value_type": row["value_type"],
            "code": row["observation_code"],
            "display": row["observation_text"] or row["observation_code"],
            "value": row["observation_value"],
            "units": row["units"],
            "reference_range": row["reference_range"],
            "abnormal_flag": row["abnormal_flag"],
            "result_status": row["result_status"],
        },
        "expected": {"ack_code": "AA"},
    }


def mark_delivery(row: dict, status: str, *, error: str = "", persisted=None, db_container: str) -> None:
    control_id = ""
    report_count = "NULL"
    result_count = "NULL"
    if persisted:
        control_id = persisted.get("control_id", "")
        report_count = int(persisted.get("report_count", 1))
        result_count = int(persisted.get("result_count", 1))
    run_psql(
        f"""
        UPDATE audit.openemr_oru_deliveries
           SET delivery_status = {sql_literal(status)},
               delivered_at = CASE WHEN {sql_literal(status)} = 'DELIVERED'
                                   THEN CURRENT_TIMESTAMP ELSE delivered_at END,
               last_error = NULLIF({sql_literal(error)}, ''),
               openemr_control_id = NULLIF({sql_literal(control_id)}, ''),
               report_count = {report_count}, result_count = {result_count},
               updated_at = CURRENT_TIMESTAMP
         WHERE delivery_id = {int(row['delivery_id'])};
        """,
        container=db_container,
    )


def deliver(args: argparse.Namespace) -> None:
    row = claim_delivery(args)
    if args.confirm_order_id != int(row["order_id"]):
        mark_delivery(row, "FAILED", error="Order confirmation mismatch", db_container=args.db_container)
        raise ValueError(
            "Delivery requires --confirm-order-id matching "
            f"Order ID {row['order_id']}."
        )
    scenario = scenario_from_delivery(row)
    target = OpenEmrTarget(
        order_id=int(row["order_id"]), patient_id=int(row["patient_id"]),
        encounter_id=int(row["encounter_id"]), lab_id=int(row["lab_id"]),
    )
    try:
        with tempfile.TemporaryDirectory(prefix="openemr-oru-") as temp_dir:
            path = Path(temp_dir) / "scenario.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            result = execute_openemr_scenario(
                path, target, commit=True,
                confirm_order_id=target.order_id,
                container=args.openemr_container,
            )
        persisted = result.committed["persisted"]
        ledger_result = {
            **persisted,
            "control_id": row["filler_order_number"],
            "report_count": 1,
            "result_count": 1,
        }
        mark_delivery(row, "DELIVERED", persisted=ledger_result, db_container=args.db_container)
    except Exception as exc:
        mark_delivery(row, "FAILED", error=str(exc), db_container=args.db_container)
        raise
    print(json.dumps({"status": "DELIVERED", "delivery_id": row["delivery_id"], "order_id": row["order_id"], "persisted": persisted}, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Deliver accepted Mirth ORUs to guarded OpenEMR ingestion.")
    root.add_argument("--db-container", default=DEFAULT_DB_CONTAINER)
    sub = root.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register-target")
    for name in ("order-id", "patient-id", "encounter-id", "lab-id", "confirm-order-id"):
        register.add_argument(f"--{name}", type=int, required=True)
    register.add_argument("--placer-order", required=True)
    register.add_argument("--patient-identifier", required=True)
    register.add_argument("--patient-family-name", required=True)
    register.add_argument("--patient-given-name", required=True)
    register.add_argument("--patient-date-of-birth", required=True)
    register.add_argument("--patient-sex", required=True)
    delivery = sub.add_parser("deliver")
    delivery.add_argument("--delivery-id", type=int)
    delivery.add_argument("--confirm-order-id", type=int, required=True)
    delivery.add_argument("--openemr-container", default="health-it-openemr-lab-openemr-1")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        register_target(args) if args.command == "register-target" else deliver(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"MIRTH TO OPENEMR DELIVERY: FAIL - {exc}")
        return 1
    print("MIRTH TO OPENEMR DELIVERY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
