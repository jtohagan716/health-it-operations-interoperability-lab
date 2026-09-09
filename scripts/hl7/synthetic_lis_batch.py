"""Run or resume a guarded synthetic-LIS batch pilot."""

import argparse
import json
import sys
from dataclasses import dataclass

from scripts.hl7.mirth_openemr_delivery import (
    deliver_order,
    run_psql,
    sql_literal,
)
from scripts.hl7.send_openemr_lab_order import (
    send_order,
)
from scripts.hl7.synthetic_lis import (
    process_order,
)
from scripts.synthetic.laboratory_orders import (
    execute as verify_laboratory_orders,
)


MAXIMUM_PILOT_SIZE = 10

RESUMABLE_LIS_STATES = {
    "RECEIVED",
    "FAILED",
    "RESULT_ACKED",
}


@dataclass(frozen=True)
class BatchOrder:
    placer_order_number: str
    openemr_order_id: int
    patient_identifier: str


def existing_lis_orders() -> set[str]:
    output = run_psql("""
        SELECT placer_order_number
          FROM lis.orders
         ORDER BY placer_order_number;
    """)

    return {
        line.strip()
        for line in output.splitlines()
        if line.strip()
    }


def get_lis_order_state(
    placer_order_number: str,
    *,
    db_container: str = (
        "health-it-mirth-lab-interop-db-1"
    ),
) -> dict | None:
    output = run_psql(
        f"""
        SELECT row_to_json(state)
          FROM (
            SELECT
                   o.lis_order_id,
                   o.placer_order_number,
                   o.order_status,
                   o.result_attempt_count,
                   o.result_message_control_id,
                   o.result_ack_code,
                   o.result_ack_control_id,
                   m.oru_message_id,
                   m.message_control_id AS
                       oru_control_id,
                   m.processing_status AS
                       oru_processing_status,
                   d.delivery_id,
                   d.delivery_status
              FROM lis.orders o
              LEFT JOIN LATERAL (
                   SELECT
                          om.oru_message_id,
                          om.message_control_id,
                          om.processing_status
                     FROM audit.oru_messages om
                    WHERE om.placer_order_number =
                          o.placer_order_number
                      AND om.message_control_id =
                          o.result_message_control_id
                    ORDER BY om.oru_message_id DESC
                    LIMIT 1
              ) m ON TRUE
              LEFT JOIN LATERAL (
                   SELECT
                          od.delivery_id,
                          od.delivery_status
                     FROM audit.openemr_oru_deliveries od
                    WHERE od.oru_message_id =
                          m.oru_message_id
                    ORDER BY od.delivery_id DESC
                    LIMIT 1
              ) d ON TRUE
             WHERE o.placer_order_number =
                   {sql_literal(
                       placer_order_number
                   )}
          ) state;
        """,
        container=db_container,
    )

    rows = [
        line
        for line in output.splitlines()
        if line.startswith("{")
    ]

    if not rows:
        return None

    return json.loads(rows[-1])


def verified_openemr_orders() -> dict:
    result = verify_laboratory_orders(
        verify_only=True,
    )

    records = result.get("records")

    if not isinstance(records, dict):
        raise RuntimeError(
            "Verified laboratory-order output "
            "does not contain a records object."
        )

    return records


def batch_order_from_record(
    external_id: str,
    row: dict,
) -> BatchOrder:
    order_id = row.get("order_id")
    patient_identifier = row.get("mrn")

    if order_id in (None, ""):
        raise RuntimeError(
            "Verified order "
            f"{external_id} has no order_id."
        )

    if patient_identifier in (None, ""):
        raise RuntimeError(
            "Verified order "
            f"{external_id} has no MRN."
        )

    return BatchOrder(
        placer_order_number=external_id,
        openemr_order_id=int(order_id),
        patient_identifier=str(
            patient_identifier
        ),
    )


def select_batch_orders(
    *,
    limit: int,
) -> list[BatchOrder]:
    if limit < 1:
        raise ValueError(
            "--limit must be at least 1."
        )

    if limit > MAXIMUM_PILOT_SIZE:
        raise ValueError(
            "--limit cannot exceed the pilot "
            f"maximum of {MAXIMUM_PILOT_SIZE}."
        )

    records = verified_openemr_orders()
    existing = existing_lis_orders()
    candidates = []

    for external_id in sorted(records):
        if external_id in existing:
            continue

        candidates.append(
            batch_order_from_record(
                external_id,
                records[external_id],
            )
        )

        if len(candidates) == limit:
            break

    if len(candidates) != limit:
        raise RuntimeError(
            f"Requested {limit} fresh orders, "
            f"but only {len(candidates)} are "
            "available."
        )

    return candidates


def select_resume_order(
    placer_order_number: str,
    *,
    db_container: str,
) -> tuple[BatchOrder, dict]:
    records = verified_openemr_orders()

    if placer_order_number not in records:
        raise ValueError(
            "Cannot resume unknown verified "
            f"order {placer_order_number}."
        )

    state = get_lis_order_state(
        placer_order_number,
        db_container=db_container,
    )

    if state is None:
        raise ValueError(
            "Cannot resume placer order "
            f"{placer_order_number}: no durable "
            "LIS state exists."
        )

    order_status = state.get("order_status")

    if order_status not in RESUMABLE_LIS_STATES:
        raise ValueError(
            "Cannot resume placer order "
            f"{placer_order_number} from LIS "
            f"state {order_status}."
        )

    order = batch_order_from_record(
        placer_order_number,
        records[placer_order_number],
    )

    return order, state


def validate_commit_confirmation(
    *,
    commit: bool,
    limit: int,
    confirm_order_count: int | None,
) -> None:
    if not commit:
        return

    if confirm_order_count is None:
        raise ValueError(
            "--commit requires "
            "--confirm-order-count."
        )

    if confirm_order_count != limit:
        raise ValueError(
            "--confirm-order-count must match "
            f"the selected count exactly ({limit})."
        )


def planned_order(
    order: BatchOrder,
    *,
    durable_state: dict | None = None,
) -> dict:
    result = {
        "placer_order_number": (
            order.placer_order_number
        ),
        "openemr_order_id": (
            order.openemr_order_id
        ),
        "patient_identifier": (
            order.patient_identifier
        ),
    }

    if durable_state is not None:
        result["durable_state"] = durable_state

    return result


def reconciled_oml_outcome(
    order: BatchOrder,
    *,
    transport_error: str,
    db_container: str,
) -> dict | None:
    state = get_lis_order_state(
        order.placer_order_number,
        db_container=db_container,
    )

    if (
        state is None
        or state.get("order_status")
        != "RECEIVED"
    ):
        return None

    return {
        "status": (
            "ACCEPTED_AFTER_RECONCILIATION"
        ),
        "placer_order_number": (
            order.placer_order_number
        ),
        "openemr_order_id": (
            order.openemr_order_id
        ),
        "lis_order_id": state[
            "lis_order_id"
        ],
        "durable_order_status": state[
            "order_status"
        ],
        "transport_error": transport_error,
    }


def reconcile_accepted_result(
    order: BatchOrder,
    *,
    state: dict,
    db_container: str,
) -> dict | None:
    result_control_id = state.get(
        "result_message_control_id"
    )

    if (
        state.get("order_status") != "FAILED"
        or not result_control_id
        or state.get("oru_control_id")
        != result_control_id
        or state.get("oru_processing_status")
        != "ACCEPTED"
        or state.get("oru_message_id") is None
    ):
        return None

    output = run_psql(
        f"""
        UPDATE lis.orders o
           SET order_status = 'RESULT_ACKED',
               result_ack_code = 'AA',
               result_ack_control_id =
                   o.result_message_control_id,
               last_error = NULL,
               updated_at = CURRENT_TIMESTAMP
         WHERE o.lis_order_id =
               {int(state["lis_order_id"])}
           AND o.placer_order_number =
               {sql_literal(
                   order.placer_order_number
               )}
           AND o.order_status = 'FAILED'
           AND o.result_message_control_id =
               {sql_literal(result_control_id)}
           AND EXISTS (
               SELECT 1
                 FROM audit.oru_messages m
                WHERE m.oru_message_id =
                      {int(state["oru_message_id"])}
                  AND m.message_control_id =
                      o.result_message_control_id
                  AND m.placer_order_number =
                      o.placer_order_number
                  AND m.processing_status =
                      'ACCEPTED'
           )
        RETURNING lis_order_id;
        """,
        container=db_container,
    )

    updated_ids = [
        line.strip()
        for line in output.splitlines()
        if line.strip().isdigit()
    ]

    if updated_ids != [
        str(state["lis_order_id"])
    ]:
        return None

    return {
        "status": (
            "RESULT_ACKED_AFTER_DURABLE_ACCEPTANCE"
        ),
        "lis_order_id": state["lis_order_id"],
        "placer_order_number": (
            order.placer_order_number
        ),
        "result_message_control_id": (
            result_control_id
        ),
        "ack_code": "AA",
        "ack_control_id": result_control_id,
        "evidence": {
            "oru_message_id": state[
                "oru_message_id"
            ],
            "oru_processing_status": "ACCEPTED",
            "delivery_id": state.get(
                "delivery_id"
            ),
            "delivery_status": state.get(
                "delivery_status"
            ),
        },
    }


def process_batch_order(
    order: BatchOrder,
    *,
    oml_host: str,
    oml_port: int,
    oru_host: str,
    oru_port: int,
    db_container: str,
    openemr_container: str,
    resume_state: dict | None = None,
) -> dict:
    result = {
        **planned_order(
            order,
            durable_state=resume_state,
        ),
        "status": "IN_PROGRESS",
        "completed_stage": None,
    }

    try:
        if resume_state is None:
            try:
                oml = send_order(
                    order.placer_order_number,
                    confirm_order_id=(
                        order.openemr_order_id
                    ),
                    host=oml_host,
                    port=oml_port,
                )
            except Exception as exc:
                oml = reconciled_oml_outcome(
                    order,
                    transport_error=str(exc),
                    db_container=db_container,
                )

                if oml is None:
                    raise

            result["oml"] = oml
            result["completed_stage"] = (
                oml["status"]
            )
            current_lis_state = "RECEIVED"
            delivery_status = None
        else:
            current_lis_state = resume_state[
                "order_status"
            ]
            delivery_status = resume_state.get(
                "delivery_status"
            )
            result["oml"] = {
                "status": (
                    "SKIPPED_DURABLE_LIS_STATE"
                ),
                "durable_order_status": (
                    current_lis_state
                ),
            }
            result["completed_stage"] = (
                "OML_ALREADY_ACCEPTED"
            )

        if (
            current_lis_state == "FAILED"
            and resume_state.get(
                "oru_processing_status"
            ) == "ACCEPTED"
        ):
            lis = reconcile_accepted_result(
                order,
                state=resume_state,
                db_container=db_container,
            )

            if lis is None:
                raise RuntimeError(
                    "Could not reconcile accepted "
                    "ORU for "
                    f"{order.placer_order_number}."
                )

            result["lis"] = lis
            result["completed_stage"] = (
                "RESULT_ACKED_AFTER_RECONCILIATION"
            )
            current_lis_state = "RESULT_ACKED"

        if "lis" in result:
            pass
        elif (
            current_lis_state
            in {"RECEIVED", "FAILED"}
        ):
            lis = process_order(
                placer_order_number=(
                    order.placer_order_number
                ),
                host=oru_host,
                oru_port=oru_port,
            )
            result["lis"] = lis
            result["completed_stage"] = (
                "RESULT_ACKED"
            )
        elif current_lis_state == "RESULT_ACKED":
            result["lis"] = {
                "status": (
                    "SKIPPED_DURABLE_RESULT"
                ),
                "durable_order_status": (
                    current_lis_state
                ),
            }
            result["completed_stage"] = (
                "RESULT_ALREADY_ACKED"
            )
        else:
            raise RuntimeError(
                "Unsupported LIS state "
                f"{current_lis_state} for "
                f"{order.placer_order_number}."
            )

        if delivery_status == "DELIVERED":
            result["delivery"] = {
                "status": (
                    "SKIPPED_DURABLE_DELIVERY"
                ),
                "durable_delivery_status": (
                    delivery_status
                ),
            }
            result["completed_stage"] = (
                "OPENEMR_ALREADY_DELIVERED"
            )
        else:
            delivery = deliver_order(
                placer_order_number=(
                    order.placer_order_number
                ),
                confirm_order_id=(
                    order.openemr_order_id
                ),
                db_container=db_container,
                openemr_container=(
                    openemr_container
                ),
            )
            result["delivery"] = delivery
            result["completed_stage"] = (
                "OPENEMR_DELIVERED"
            )

        result["status"] = "COMPLETED"

    except Exception as exc:
        result["status"] = "FAILED"
        result["error"] = str(exc)

    return result


def execute_batch(
    *,
    limit: int | None = None,
    resume_placer_order: str | None = None,
    commit: bool = False,
    confirm_order_count: int | None = None,
    continue_on_error: bool = False,
    oml_host: str = "localhost",
    oml_port: int = 6664,
    oru_host: str = "localhost",
    oru_port: int = 6662,
    db_container: str = (
        "health-it-mirth-lab-interop-db-1"
    ),
    openemr_container: str = (
        "health-it-openemr-lab-openemr-1"
    ),
) -> dict:
    if (
        limit is None
        and resume_placer_order is None
    ):
        raise ValueError(
            "Select fresh orders with --limit "
            "or one existing order with "
            "--resume-placer-order."
        )

    if (
        limit is not None
        and resume_placer_order is not None
    ):
        raise ValueError(
            "--limit and --resume-placer-order "
            "cannot be used together."
        )

    resume_states = {}

    if resume_placer_order is not None:
        order, state = select_resume_order(
            resume_placer_order,
            db_container=db_container,
        )
        orders = [order]
        resume_states[
            order.placer_order_number
        ] = state
        selected_count = 1
        mode = "RESUME"
    else:
        orders = select_batch_orders(
            limit=int(limit)
        )
        selected_count = int(limit)
        mode = "FRESH"

    validate_commit_confirmation(
        commit=commit,
        limit=selected_count,
        confirm_order_count=(
            confirm_order_count
        ),
    )

    if not commit:
        return {
            "status": "DRY_RUN",
            "mode": mode,
            "committed": False,
            "requested_order_count": (
                selected_count
            ),
            "selected_order_count": (
                len(orders)
            ),
            "maximum_pilot_size": (
                MAXIMUM_PILOT_SIZE
            ),
            "orders": [
                planned_order(
                    order,
                    durable_state=(
                        resume_states.get(
                            order.placer_order_number
                        )
                    ),
                )
                for order in orders
            ],
        }

    outcomes = []

    for order in orders:
        outcome = process_batch_order(
            order,
            oml_host=oml_host,
            oml_port=oml_port,
            oru_host=oru_host,
            oru_port=oru_port,
            db_container=db_container,
            openemr_container=(
                openemr_container
            ),
            resume_state=(
                resume_states.get(
                    order.placer_order_number
                )
            ),
        )
        outcomes.append(outcome)

        if (
            outcome["status"] == "FAILED"
            and not continue_on_error
        ):
            break

    completed_count = sum(
        outcome["status"] == "COMPLETED"
        for outcome in outcomes
    )
    failed_count = sum(
        outcome["status"] == "FAILED"
        for outcome in outcomes
    )

    status = (
        "COMPLETED"
        if completed_count == selected_count
        else "PARTIAL_FAILURE"
    )

    return {
        "status": status,
        "mode": mode,
        "committed": True,
        "requested_order_count": (
            selected_count
        ),
        "attempted_order_count": len(
            outcomes
        ),
        "completed_order_count": (
            completed_count
        ),
        "failed_order_count": (
            failed_count
        ),
        "continue_on_error": (
            continue_on_error
        ),
        "orders": outcomes,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=__doc__
    )

    selection = (
        result.add_mutually_exclusive_group(
            required=True
        )
    )
    selection.add_argument(
        "--limit",
        type=int,
        help=(
            "Select this many fresh orders, "
            "up to the pilot maximum."
        ),
    )
    selection.add_argument(
        "--resume-placer-order",
        help=(
            "Resume one explicitly named order "
            "from durable LIS state."
        ),
    )

    result.add_argument(
        "--commit",
        action="store_true",
    )
    result.add_argument(
        "--confirm-order-count",
        type=int,
    )
    result.add_argument(
        "--continue-on-error",
        action="store_true",
    )
    result.add_argument(
        "--oml-host",
        default="localhost",
    )
    result.add_argument(
        "--oml-port",
        type=int,
        default=6664,
    )
    result.add_argument(
        "--oru-host",
        default="localhost",
    )
    result.add_argument(
        "--oru-port",
        type=int,
        default=6662,
    )
    result.add_argument(
        "--db-container",
        default=(
            "health-it-mirth-lab-"
            "interop-db-1"
        ),
    )
    result.add_argument(
        "--openemr-container",
        default=(
            "health-it-openemr-lab-"
            "openemr-1"
        ),
    )

    return result


def main() -> int:
    args = parser().parse_args()

    try:
        outcome = execute_batch(
            limit=args.limit,
            resume_placer_order=(
                args.resume_placer_order
            ),
            commit=args.commit,
            confirm_order_count=(
                args.confirm_order_count
            ),
            continue_on_error=(
                args.continue_on_error
            ),
            oml_host=args.oml_host,
            oml_port=args.oml_port,
            oru_host=args.oru_host,
            oru_port=args.oru_port,
            db_container=args.db_container,
            openemr_container=(
                args.openemr_container
            ),
        )
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            "SYNTHETIC LIS BATCH: "
            f"FAIL - {exc}"
        )
        return 1

    print(json.dumps(outcome, indent=2))

    if outcome["status"] == "PARTIAL_FAILURE":
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
