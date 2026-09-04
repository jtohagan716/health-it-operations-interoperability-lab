import argparse
import json
import sys

from scripts.hl7.oml_order import build_oml_segments, load_verified_order
from scripts.hl7.scenario_runtime import send_segments
from scripts.hl7.mirth_openemr_delivery import run_psql, sql_literal


def register_target(order) -> None:
    run_psql(f"""
        INSERT INTO audit.openemr_oru_targets (
            placer_order_number, openemr_order_id, openemr_patient_id,
            openemr_encounter_id, openemr_lab_id, patient_identifier,
            patient_family_name, patient_given_name, patient_date_of_birth,
            patient_administrative_sex
        ) VALUES (
            {sql_literal(order.placer_order_number)}, {order.order_id},
            {order.patient_id}, {order.encounter_id}, {order.lab_id},
            {sql_literal(order.patient_identifier)},
            {sql_literal(order.patient_family_name)},
            {sql_literal(order.patient_given_name)},
            {sql_literal(order.patient_date_of_birth)},
            {sql_literal(order.patient_sex)}
        ) ON CONFLICT (placer_order_number) DO UPDATE SET
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
    """)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a verified OpenEMR order to the synthetic LIS.")
    parser.add_argument("--order", default="SYNLAB00000101")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6664)
    parser.add_argument("--control-id")
    parser.add_argument("--confirm-order-id", type=int, required=True)
    args = parser.parse_args()
    control_id = args.control_id or f"SYNLIS-OML-{args.order}-01"
    try:
        order = load_verified_order(args.order)
        if args.confirm_order_id != order.order_id:
            raise ValueError(
                f"--confirm-order-id must match OpenEMR order {order.order_id}."
            )
        register_target(order)
        segments = build_oml_segments(order, control_id=control_id)
        ack = send_segments(segments, host=args.host, port=args.port)
        if not ack.accepted:
            raise RuntimeError(f"Mirth rejected OML with {ack.code}.")
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"OPENEMR LAB ORDER TRANSPORT: FAIL - {exc}")
        return 1
    print(json.dumps({
        "status": "ACCEPTED", "placer_order_number": args.order,
        "message_control_id": control_id, "ack_code": ack.code,
        "ack_control_id": ack.control_id,
        "ack_round_trip_seconds": round(ack.round_trip_seconds, 3),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
