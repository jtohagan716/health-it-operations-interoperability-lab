import argparse
import json
import sys
from datetime import datetime, timedelta

from scripts.hl7.oru_scenario import build_oru_segments
from scripts.hl7.scenario_runtime import run_psql, send_segments


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def claim_order(
    *,
    placer_order_number: str | None = None,
) -> dict:
    selector = (
        "TRUE"
        if placer_order_number is None
        else (
            "placer_order_number = "
            f"{sql_literal(placer_order_number)}"
        )
    )

    output = run_psql(f"""
        BEGIN;
        WITH candidate AS (
            SELECT lis_order_id
              FROM lis.orders
             WHERE order_status IN ('RECEIVED', 'FAILED')
               AND {selector}
             ORDER BY received_at, lis_order_id
             FOR UPDATE SKIP LOCKED
             LIMIT 1
        ), claimed AS (
            UPDATE lis.orders o
               SET order_status = 'IN_PROGRESS',
                   result_attempt_count =
                       result_attempt_count + 1,
                   last_error = NULL,
                   updated_at = CURRENT_TIMESTAMP
              FROM candidate c
             WHERE o.lis_order_id = c.lis_order_id
         RETURNING o.*
        )
        SELECT row_to_json(claimed)
          FROM claimed;
        COMMIT;
    """)

    rows = [
        line
        for line in output.splitlines()
        if line.startswith("{")
    ]

    if not rows:
        if placer_order_number is None:
            raise RuntimeError(
                "No eligible synthetic LIS order "
                "is available."
            )

        raise RuntimeError(
            "No eligible synthetic LIS order is "
            "available for placer order "
            f"{placer_order_number}."
        )

    return json.loads(rows[-1])


def deterministic_glucose(
    patient_identifier: str,
) -> tuple[str, str]:
    value = 82 + (
        sum(patient_identifier.encode("utf-8"))
        % 17
    )
    return str(value), "N"


def deterministic_result_timestamp(
    clinical_order_at: str,
) -> str:
    normalized = clinical_order_at.replace(
        "Z",
        "+00:00",
    )
    result_at = (
        datetime.fromisoformat(normalized)
        + timedelta(minutes=30)
    )
    return result_at.strftime("%Y%m%d%H%M%S")


def scenario_from_order(row: dict) -> dict:
    value, flag = deterministic_glucose(
        row["patient_identifier"]
    )
    control_id = (
        "SYNLIS-ORU-"
        f"{row['lis_order_id']:06d}-01"
    )
    timestamp = deterministic_result_timestamp(
        row["clinical_order_at"]
    )

    return {
        "scenario_id": (
            f"synthetic-lis-{row['lis_order_id']}"
        ),
        "message": {
            "timestamp": timestamp,
            "control_id": control_id,
            "sending_application": "SYNLIS",
            "sending_facility": "LAB",
        },
        "patient": {
            "identifier": row[
                "patient_identifier"
            ],
            "family_name": row[
                "patient_family_name"
            ],
            "given_name": row[
                "patient_given_name"
            ],
            "date_of_birth": row[
                "patient_date_of_birth"
            ],
            "administrative_sex": row[
                "patient_administrative_sex"
            ],
        },
        "order": {
            "placer_number": row[
                "placer_order_number"
            ],
            "filler_number": row[
                "filler_order_number"
            ],
            "service_code": row["service_code"],
            "service_display": row["service_text"],
            "observation_timestamp": timestamp,
            "result_status": "F",
        },
        "observation": {
            "value_type": "NM",
            "code": row["service_code"],
            "display": row["service_text"],
            "value": value,
            "units": "mg/dL",
            "reference_range": "70-99",
            "abnormal_flag": flag,
            "result_status": "F",
        },
        "expected": {
            "ack_code": "AA",
        },
    }


def update_result(
    row: dict,
    scenario: dict,
    acknowledgment,
    *,
    error: str = "",
) -> None:
    status = (
        "RESULT_ACKED"
        if acknowledgment
        and acknowledgment.accepted
        else "FAILED"
    )
    observation = scenario["observation"]

    run_psql(f"""
        UPDATE lis.orders
           SET order_status =
                   {sql_literal(status)},
               result_message_control_id =
                   {sql_literal(
                       scenario["message"]["control_id"]
                   )},
               result_value =
                   {observation["value"]},
               result_units =
                   {sql_literal(observation["units"])},
               result_reference_range =
                   {sql_literal(
                       observation["reference_range"]
                   )},
               result_abnormal_flag =
                   {sql_literal(
                       observation["abnormal_flag"]
                   )},
               result_status =
                   {sql_literal(
                       observation["result_status"]
                   )},
               result_ack_code =
                   {sql_literal(
                       acknowledgment.code
                       if acknowledgment
                       else ""
                   )},
               result_ack_control_id =
                   {sql_literal(
                       acknowledgment.control_id
                       if acknowledgment
                       else ""
                   )},
               last_error =
                   NULLIF(
                       {sql_literal(error)},
                       ''
                   ),
               result_sent_at = CURRENT_TIMESTAMP,
               updated_at = CURRENT_TIMESTAMP
         WHERE lis_order_id =
               {int(row["lis_order_id"])};
    """)


def process_order(
    *,
    placer_order_number: str | None = None,
    host: str = "localhost",
    oru_port: int = 6662,
) -> dict:
    row = claim_order(
        placer_order_number=placer_order_number
    )
    scenario = scenario_from_order(row)
    acknowledgment = None

    try:
        acknowledgment = send_segments(
            build_oru_segments(scenario),
            host=host,
            port=oru_port,
        )

        if not acknowledgment.accepted:
            raise RuntimeError(
                "Mirth rejected ORU with "
                f"{acknowledgment.code}."
            )

        update_result(
            row,
            scenario,
            acknowledgment,
        )
    except Exception as exc:
        update_result(
            row,
            scenario,
            acknowledgment,
            error=str(exc),
        )
        raise

    return {
        "status": "RESULT_ACKED",
        "lis_order_id": row["lis_order_id"],
        "placer_order_number": row[
            "placer_order_number"
        ],
        "filler_order_number": row[
            "filler_order_number"
        ],
        "result_message_control_id": scenario[
            "message"
        ]["control_id"],
        "result_value": scenario[
            "observation"
        ]["value"],
        "ack_code": acknowledgment.code,
        "ack_control_id": (
            acknowledgment.control_id
        ),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Process one persistent synthetic "
            "LIS order."
        )
    )
    result.add_argument(
        "--placer-order",
        help=(
            "Claim only the eligible LIS order "
            "with this placer order number."
        ),
    )
    result.add_argument(
        "--host",
        default="localhost",
    )
    result.add_argument(
        "--oru-port",
        type=int,
        default=6662,
    )
    return result


def main() -> int:
    args = parser().parse_args()

    try:
        outcome = process_order(
            placer_order_number=args.placer_order,
            host=args.host,
            oru_port=args.oru_port,
        )
    except Exception as exc:
        print(f"SYNTHETIC LIS: FAIL - {exc}")
        return 1

    print(json.dumps(outcome, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())