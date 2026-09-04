import argparse
import json
import sys

from scripts.hl7.oru_scenario import build_oru_segments
from scripts.hl7.scenario_runtime import run_psql, send_segments


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def claim_order() -> dict:
    output = run_psql("""
        BEGIN;
        WITH candidate AS (
            SELECT lis_order_id FROM lis.orders
             WHERE order_status IN ('RECEIVED', 'FAILED')
             ORDER BY received_at, lis_order_id
             FOR UPDATE SKIP LOCKED LIMIT 1
        ), claimed AS (
            UPDATE lis.orders o
               SET order_status = 'IN_PROGRESS',
                   result_attempt_count = result_attempt_count + 1,
                   last_error = NULL,
                   updated_at = CURRENT_TIMESTAMP
              FROM candidate c WHERE o.lis_order_id = c.lis_order_id
          RETURNING o.*
        ) SELECT row_to_json(claimed) FROM claimed;
        COMMIT;
    """)
    rows = [line for line in output.splitlines() if line.startswith("{")]
    if not rows:
        raise RuntimeError("No eligible synthetic LIS order is available.")
    return json.loads(rows[-1])


def deterministic_glucose(patient_identifier: str) -> tuple[str, str]:
    value = 82 + (sum(patient_identifier.encode("utf-8")) % 17)
    return str(value), "N"


def scenario_from_order(row: dict) -> dict:
    value, flag = deterministic_glucose(row["patient_identifier"])
    control_id = f"SYNLIS-ORU-{row['lis_order_id']:06d}-01"
    timestamp = row["received_at"].replace("-", "").replace(":", "")
    timestamp = timestamp.replace("T", "").replace(" ", "")[:14]
    return {
        "scenario_id": f"synthetic-lis-{row['lis_order_id']}",
        "message": {
            "timestamp": timestamp,
            "control_id": control_id,
            "sending_application": "SYNLIS",
            "sending_facility": "LAB",
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
            "service_display": row["service_text"],
            "observation_timestamp": timestamp, "result_status": "F",
        },
        "observation": {
            "value_type": "NM", "code": row["service_code"],
            "display": row["service_text"], "value": value,
            "units": "mg/dL", "reference_range": "70-99",
            "abnormal_flag": flag, "result_status": "F",
        },
        "expected": {"ack_code": "AA"},
    }


def update_result(row: dict, scenario: dict, ack, *, error: str = "") -> None:
    status = "RESULT_ACKED" if ack and ack.accepted else "FAILED"
    observation = scenario["observation"]
    run_psql(f"""
        UPDATE lis.orders SET
            order_status = {sql_literal(status)},
            result_message_control_id = {sql_literal(scenario['message']['control_id'])},
            result_value = {observation['value']},
            result_units = {sql_literal(observation['units'])},
            result_reference_range = {sql_literal(observation['reference_range'])},
            result_abnormal_flag = {sql_literal(observation['abnormal_flag'])},
            result_status = {sql_literal(observation['result_status'])},
            result_ack_code = {sql_literal(ack.code if ack else '')},
            result_ack_control_id = {sql_literal(ack.control_id if ack else '')},
            last_error = NULLIF({sql_literal(error)}, ''),
            result_sent_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE lis_order_id = {int(row['lis_order_id'])};
    """)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one persistent synthetic LIS order.")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--oru-port", type=int, default=6662)
    args = parser.parse_args()
    row = claim_order()
    scenario = scenario_from_order(row)
    try:
        ack = send_segments(build_oru_segments(scenario), host=args.host, port=args.oru_port)
        update_result(row, scenario, ack)
        if not ack.accepted:
            raise RuntimeError(f"Mirth rejected ORU with {ack.code}.")
    except Exception as exc:
        update_result(row, scenario, None, error=str(exc))
        print(f"SYNTHETIC LIS: FAIL - {exc}")
        return 1
    print(json.dumps({
        "status": "RESULT_ACKED", "lis_order_id": row["lis_order_id"],
        "placer_order_number": row["placer_order_number"],
        "filler_order_number": row["filler_order_number"],
        "result_message_control_id": scenario["message"]["control_id"],
        "result_value": scenario["observation"]["value"],
        "ack_code": ack.code, "ack_control_id": ack.control_id,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
