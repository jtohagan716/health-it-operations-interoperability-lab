import argparse
import json
import sys

from scripts.hl7.mirth_openemr_delivery import run_psql, sql_literal
from scripts.hl7.oml_order import build_oml_segments, load_verified_order
from scripts.hl7.scenario_runtime import send_segments


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
            patient_administrative_sex =
                EXCLUDED.patient_administrative_sex,
            active = TRUE;
    """)


def send_order(
    external_id: str,
    *,
    confirm_order_id: int,
    host: str = "localhost",
    port: int = 6664,
    control_id: str | None = None,
) -> dict:
    resolved_control_id = (
        control_id
        or f"SYNLIS-OML-{external_id}-01"
    )

    order = load_verified_order(external_id)

    if confirm_order_id != order.order_id:
        raise ValueError(
            "--confirm-order-id must match "
            f"OpenEMR order {order.order_id}."
        )

    register_target(order)

    segments = build_oml_segments(
        order,
        control_id=resolved_control_id,
    )

    acknowledgment = send_segments(
        segments,
        host=host,
        port=port,
    )

    if not acknowledgment.accepted:
        raise RuntimeError(
            "Mirth rejected OML with "
            f"{acknowledgment.code}."
        )

    return {
        "status": "ACCEPTED",
        "placer_order_number": external_id,
        "openemr_order_id": order.order_id,
        "message_control_id": resolved_control_id,
        "ack_code": acknowledgment.code,
        "ack_control_id": acknowledgment.control_id,
        "ack_round_trip_seconds": round(
            acknowledgment.round_trip_seconds,
            3,
        ),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Send a verified OpenEMR order "
            "to the synthetic LIS."
        )
    )
    result.add_argument(
        "--order",
        default="SYNLAB00000101",
    )
    result.add_argument(
        "--host",
        default="localhost",
    )
    result.add_argument(
        "--port",
        type=int,
        default=6664,
    )
    result.add_argument("--control-id")
    result.add_argument(
        "--confirm-order-id",
        type=int,
        required=True,
    )
    return result


def main() -> int:
    args = parser().parse_args()

    try:
        outcome = send_order(
            args.order,
            confirm_order_id=args.confirm_order_id,
            host=args.host,
            port=args.port,
            control_id=args.control_id,
        )
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            "OPENEMR LAB ORDER TRANSPORT: "
            f"FAIL - {exc}"
        )
        return 1

    print(json.dumps(outcome, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())