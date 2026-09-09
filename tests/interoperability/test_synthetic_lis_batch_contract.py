from types import SimpleNamespace

import pytest

from scripts.hl7 import send_openemr_lab_order
from scripts.hl7 import synthetic_lis
from scripts.hl7 import synthetic_lis_batch


def accepted_ack() -> SimpleNamespace:
    return SimpleNamespace(
        accepted=True,
        code="AA",
        control_id="CONTROL-1",
        round_trip_seconds=0.125,
    )


def batch_order(
    number: int,
) -> synthetic_lis_batch.BatchOrder:
    return synthetic_lis_batch.BatchOrder(
        placer_order_number=(
            f"SYNLAB{number:06d}01"
        ),
        openemr_order_id=number + 5,
        patient_identifier=(
            f"SYNTHMRN{number:06d}"
        ),
    )


def test_send_order_requires_exact_confirmation(
    monkeypatch,
):
    order = SimpleNamespace(order_id=7)

    monkeypatch.setattr(
        send_openemr_lab_order,
        "load_verified_order",
        lambda external_id: order,
    )

    with pytest.raises(
        ValueError,
        match="OpenEMR order 7",
    ):
        send_openemr_lab_order.send_order(
            "SYNLAB00000201",
            confirm_order_id=8,
        )


def test_send_order_returns_structured_outcome(
    monkeypatch,
):
    order = SimpleNamespace(order_id=7)
    registered = []

    monkeypatch.setattr(
        send_openemr_lab_order,
        "load_verified_order",
        lambda external_id: order,
    )
    monkeypatch.setattr(
        send_openemr_lab_order,
        "register_target",
        registered.append,
    )
    monkeypatch.setattr(
        send_openemr_lab_order,
        "build_oml_segments",
        lambda order, control_id: ["MSH"],
    )
    monkeypatch.setattr(
        send_openemr_lab_order,
        "send_segments",
        lambda segments, host, port: (
            accepted_ack()
        ),
    )

    outcome = (
        send_openemr_lab_order.send_order(
            "SYNLAB00000201",
            confirm_order_id=7,
            control_id="CONTROL-1",
        )
    )

    assert registered == [order]
    assert outcome["status"] == "ACCEPTED"
    assert outcome["openemr_order_id"] == 7
    assert outcome["ack_code"] == "AA"
    assert (
        outcome["ack_control_id"]
        == "CONTROL-1"
    )


def test_process_order_targets_placer_order(
    monkeypatch,
):
    row = {
        "lis_order_id": 3,
        "placer_order_number": (
            "SYNLAB00000201"
        ),
        "filler_order_number": (
            "SYNLIS-SYNLAB00000201"
        ),
    }
    scenario = {
        "message": {
            "control_id": (
                "SYNLIS-ORU-000003-01"
            ),
        },
        "observation": {
            "value": "97",
        },
    }
    claimed = []
    updates = []

    def claim_order(
        *,
        placer_order_number=None,
    ):
        claimed.append(placer_order_number)
        return row

    monkeypatch.setattr(
        synthetic_lis,
        "claim_order",
        claim_order,
    )
    monkeypatch.setattr(
        synthetic_lis,
        "scenario_from_order",
        lambda claimed_row: scenario,
    )
    monkeypatch.setattr(
        synthetic_lis,
        "build_oru_segments",
        lambda value: ["MSH"],
    )
    monkeypatch.setattr(
        synthetic_lis,
        "send_segments",
        lambda segments, host, port: (
            accepted_ack()
        ),
    )
    monkeypatch.setattr(
        synthetic_lis,
        "update_result",
        lambda *args, **kwargs: (
            updates.append((args, kwargs))
        ),
    )

    outcome = synthetic_lis.process_order(
        placer_order_number=(
            "SYNLAB00000201"
        ),
    )

    assert claimed == ["SYNLAB00000201"]
    assert len(updates) == 1
    assert outcome["status"] == "RESULT_ACKED"
    assert outcome["lis_order_id"] == 3
    assert (
        outcome["placer_order_number"]
        == "SYNLAB00000201"
    )
    assert outcome["ack_code"] == "AA"


def test_process_order_records_failure(
    monkeypatch,
):
    row = {
        "lis_order_id": 4,
        "placer_order_number": (
            "SYNLAB00000401"
        ),
    }
    scenario = {
        "message": {
            "control_id": (
                "SYNLIS-ORU-000004-01"
            ),
        },
        "observation": {
            "value": "90",
        },
    }
    updates = []

    monkeypatch.setattr(
        synthetic_lis,
        "claim_order",
        lambda **kwargs: row,
    )
    monkeypatch.setattr(
        synthetic_lis,
        "scenario_from_order",
        lambda claimed_row: scenario,
    )
    monkeypatch.setattr(
        synthetic_lis,
        "build_oru_segments",
        lambda value: ["MSH"],
    )

    def reject(*args, **kwargs):
        raise RuntimeError(
            "ORU transport failed"
        )

    monkeypatch.setattr(
        synthetic_lis,
        "send_segments",
        reject,
    )
    monkeypatch.setattr(
        synthetic_lis,
        "update_result",
        lambda *args, **kwargs: (
            updates.append((args, kwargs))
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="ORU transport failed",
    ):
        synthetic_lis.process_order(
            placer_order_number=(
                "SYNLAB00000401"
            ),
        )

    assert len(updates) == 1
    assert (
        updates[0][1]["error"]
        == "ORU transport failed"
    )


def test_batch_limit_cannot_exceed_ten():
    with pytest.raises(
        ValueError,
        match="cannot exceed",
    ):
        synthetic_lis_batch.select_batch_orders(
            limit=11
        )


def test_commit_requires_exact_count_confirmation():
    with pytest.raises(
        ValueError,
        match="requires",
    ):
        synthetic_lis_batch.validate_commit_confirmation(
            commit=True,
            limit=3,
            confirm_order_count=None,
        )

    with pytest.raises(
        ValueError,
        match="must match",
    ):
        synthetic_lis_batch.validate_commit_confirmation(
            commit=True,
            limit=3,
            confirm_order_count=2,
        )


def test_fresh_commit_requires_exact_placer_confirmation():
    orders = [
        batch_order(4),
        batch_order(5),
    ]

    with pytest.raises(
        ValueError,
        match="requires",
    ):
        synthetic_lis_batch.validate_placer_confirmation(
            orders=orders,
            confirm_placer_orders=None,
        )

    with pytest.raises(
        ValueError,
        match="must match",
    ):
        synthetic_lis_batch.validate_placer_confirmation(
            orders=orders,
            confirm_placer_orders=[
                "SYNLAB00000501",
                "SYNLAB00000401",
            ],
        )

    synthetic_lis_batch.validate_placer_confirmation(
        orders=orders,
        confirm_placer_orders=[
            "SYNLAB00000401",
            "SYNLAB00000501",
        ],
    )


def test_selection_excludes_existing_lis_orders(
    monkeypatch,
):
    records = {
        "SYNLAB00000101": {
            "order_id": 6,
            "mrn": "SYNTHMRN000001",
        },
        "SYNLAB00000201": {
            "order_id": 7,
            "mrn": "SYNTHMRN000002",
        },
        "SYNLAB00000301": {
            "order_id": 8,
            "mrn": "SYNTHMRN000003",
        },
    }

    monkeypatch.setattr(
        synthetic_lis_batch,
        "verified_openemr_orders",
        lambda: records,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "existing_lis_orders",
        lambda: {"SYNLAB00000101"},
    )

    selected = (
        synthetic_lis_batch.select_batch_orders(
            limit=2
        )
    )

    assert [
        item.placer_order_number
        for item in selected
    ] == [
        "SYNLAB00000201",
        "SYNLAB00000301",
    ]
    assert [
        item.openemr_order_id
        for item in selected
    ] == [7, 8]


def test_dry_run_does_not_process_orders(
    monkeypatch,
):
    orders = [
        batch_order(4),
        batch_order(5),
    ]

    monkeypatch.setattr(
        synthetic_lis_batch,
        "select_batch_orders",
        lambda limit: orders,
    )

    def unexpected_processing(*args, **kwargs):
        raise AssertionError(
            "Dry run processed an order."
        )

    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_batch_order",
        unexpected_processing,
    )

    outcome = (
        synthetic_lis_batch.execute_batch(
            limit=2,
        )
    )

    assert outcome["status"] == "DRY_RUN"
    assert outcome["committed"] is False
    assert outcome["selected_order_count"] == 2
    assert len(outcome["orders"]) == 2
    assert outcome["commit_confirmation"] == {
        "order_count": 2,
        "placer_orders": [
            "SYNLAB00000401",
            "SYNLAB00000501",
        ],
    }


def test_batch_order_runs_all_three_stages(
    monkeypatch,
):
    order = batch_order(4)
    calls = []

    def send(
        external_id,
        **kwargs,
    ):
        calls.append(
            ("send", external_id, kwargs)
        )
        return {"status": "ACCEPTED"}

    def process(**kwargs):
        calls.append(
            ("process", kwargs)
        )
        return {"status": "RESULT_ACKED"}

    def deliver(**kwargs):
        calls.append(
            ("deliver", kwargs)
        )
        return {"status": "DELIVERED"}

    monkeypatch.setattr(
        synthetic_lis_batch,
        "send_order",
        send,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_order",
        process,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "deliver_order",
        deliver,
    )

    outcome = (
        synthetic_lis_batch.process_batch_order(
            order,
            oml_host="localhost",
            oml_port=6664,
            oru_host="localhost",
            oru_port=6662,
            db_container="interop-db",
            openemr_container="openemr",
        )
    )

    assert [
        call[0]
        for call in calls
    ] == [
        "send",
        "process",
        "deliver",
    ]
    assert outcome["status"] == "COMPLETED"
    assert (
        outcome["completed_stage"]
        == "OPENEMR_DELIVERED"
    )


def test_batch_stops_after_first_failure(
    monkeypatch,
):
    orders = [
        batch_order(4),
        batch_order(5),
    ]
    attempted = []

    monkeypatch.setattr(
        synthetic_lis_batch,
        "select_batch_orders",
        lambda limit: orders,
    )

    def fail_first(order, **kwargs):
        attempted.append(
            order.placer_order_number
        )
        return {
            "status": "FAILED",
            "error": "controlled failure",
        }

    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_batch_order",
        fail_first,
    )

    outcome = (
        synthetic_lis_batch.execute_batch(
            limit=2,
            commit=True,
            confirm_order_count=2,
            confirm_placer_orders=[
                "SYNLAB00000401",
                "SYNLAB00000501",
            ],
        )
    )

    assert outcome["status"] == (
        "PARTIAL_FAILURE"
    )
    assert outcome["attempted_order_count"] == 1
    assert outcome["failed_order_count"] == 1
    assert attempted == ["SYNLAB00000401"]

def test_oml_timeout_reconciles_durable_acceptance(
    monkeypatch,
):
    order = batch_order(4)
    stages = []

    def timeout(*args, **kwargs):
        raise RuntimeError(
            "Timed out waiting for ACK"
        )

    monkeypatch.setattr(
        synthetic_lis_batch,
        "send_order",
        timeout,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "reconciled_oml_outcome",
        lambda *args, **kwargs: {
            "status": (
                "ACCEPTED_AFTER_RECONCILIATION"
            ),
            "lis_order_id": 5,
            "durable_order_status": "RECEIVED",
            "transport_error": (
                "Timed out waiting for ACK"
            ),
        },
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_order",
        lambda **kwargs: (
            stages.append("process")
            or {"status": "RESULT_ACKED"}
        ),
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "deliver_order",
        lambda **kwargs: (
            stages.append("deliver")
            or {"status": "DELIVERED"}
        ),
    )

    outcome = (
        synthetic_lis_batch.process_batch_order(
            order,
            oml_host="localhost",
            oml_port=6664,
            oru_host="localhost",
            oru_port=6662,
            db_container="interop-db",
            openemr_container="openemr",
        )
    )

    assert outcome["status"] == "COMPLETED"
    assert outcome["oml"]["status"] == (
        "ACCEPTED_AFTER_RECONCILIATION"
    )
    assert stages == ["process", "deliver"]


def test_resume_received_skips_oml_and_continues(
    monkeypatch,
):
    order = batch_order(4)
    stages = []

    def unexpected_send(*args, **kwargs):
        raise AssertionError(
            "Resume resent the accepted OML."
        )

    monkeypatch.setattr(
        synthetic_lis_batch,
        "send_order",
        unexpected_send,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_order",
        lambda **kwargs: (
            stages.append("process")
            or {"status": "RESULT_ACKED"}
        ),
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "deliver_order",
        lambda **kwargs: (
            stages.append("deliver")
            or {"status": "DELIVERED"}
        ),
    )

    outcome = (
        synthetic_lis_batch.process_batch_order(
            order,
            oml_host="localhost",
            oml_port=6664,
            oru_host="localhost",
            oru_port=6662,
            db_container="interop-db",
            openemr_container="openemr",
            resume_state={
                "lis_order_id": 5,
                "order_status": "RECEIVED",
                "delivery_status": None,
            },
        )
    )

    assert outcome["status"] == "COMPLETED"
    assert outcome["oml"]["status"] == (
        "SKIPPED_DURABLE_LIS_STATE"
    )
    assert stages == ["process", "deliver"]

def test_resume_completed_order_performs_no_writes(
    monkeypatch,
):
    order = batch_order(4)

    def unexpected_operation(*args, **kwargs):
        raise AssertionError(
            "Completed order was processed again."
        )

    monkeypatch.setattr(
        synthetic_lis_batch,
        "send_order",
        unexpected_operation,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_order",
        unexpected_operation,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "deliver_order",
        unexpected_operation,
    )

    outcome = (
        synthetic_lis_batch.process_batch_order(
            order,
            oml_host="localhost",
            oml_port=6664,
            oru_host="localhost",
            oru_port=6662,
            db_container="interop-db",
            openemr_container="openemr",
            resume_state={
                "lis_order_id": 5,
                "order_status": "RESULT_ACKED",
                "delivery_status": "DELIVERED",
            },
        )
    )

    assert outcome["status"] == "COMPLETED"
    assert outcome["lis"]["status"] == (
        "SKIPPED_DURABLE_RESULT"
    )
    assert outcome["delivery"]["status"] == (
        "SKIPPED_DURABLE_DELIVERY"
    )
    assert outcome["completed_stage"] == (
        "OPENEMR_ALREADY_DELIVERED"
    )


def test_failed_delivered_result_is_reconciled_without_resend(
    monkeypatch,
):
    order = batch_order(4)
    calls = []
    state = {
        "lis_order_id": 5,
        "order_status": "FAILED",
        "result_message_control_id": (
            "SYNLIS-ORU-000005-01"
        ),
        "oru_message_id": 116,
        "oru_control_id": (
            "SYNLIS-ORU-000005-01"
        ),
        "oru_processing_status": "ACCEPTED",
        "delivery_id": 6,
        "delivery_status": "DELIVERED",
    }

    def unexpected_transport(*args, **kwargs):
        raise AssertionError(
            "Delivered result was transported again."
        )

    monkeypatch.setattr(
        synthetic_lis_batch,
        "send_order",
        unexpected_transport,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_order",
        unexpected_transport,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "deliver_order",
        unexpected_transport,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "reconcile_accepted_result",
        lambda *args, **kwargs: (
            calls.append("reconcile")
            or {
                "status": (
                    "RESULT_ACKED_AFTER_"
                    "DURABLE_ACCEPTANCE"
                )
            }
        ),
    )

    outcome = (
        synthetic_lis_batch.process_batch_order(
            order,
            oml_host="localhost",
            oml_port=6664,
            oru_host="localhost",
            oru_port=6662,
            db_container="interop-db",
            openemr_container="openemr",
            resume_state=state,
        )
    )

    assert calls == ["reconcile"]
    assert outcome["status"] == "COMPLETED"
    assert outcome["lis"]["status"] == (
        "RESULT_ACKED_AFTER_DURABLE_ACCEPTANCE"
    )
    assert outcome["delivery"]["status"] == (
        "SKIPPED_DURABLE_DELIVERY"
    )
    assert outcome["completed_stage"] == (
        "OPENEMR_ALREADY_DELIVERED"
    )


def test_accepted_reconciliation_requires_exact_evidence(
    monkeypatch,
):
    order = batch_order(4)
    queries = []
    state = {
        "lis_order_id": 5,
        "order_status": "FAILED",
        "result_message_control_id": (
            "SYNLIS-ORU-000005-01"
        ),
        "oru_message_id": 116,
        "oru_control_id": (
            "SYNLIS-ORU-000005-01"
        ),
        "oru_processing_status": "ACCEPTED",
        "delivery_id": 6,
        "delivery_status": "DELIVERED",
    }

    def run(query, *, container):
        queries.append((query, container))
        return "5\n"

    monkeypatch.setattr(
        synthetic_lis_batch,
        "run_psql",
        run,
    )

    outcome = (
        synthetic_lis_batch.reconcile_accepted_result(
            order,
            state=state,
            db_container="interop-db",
        )
    )

    assert outcome is not None
    assert outcome["status"] == (
        "RESULT_ACKED_AFTER_DURABLE_ACCEPTANCE"
    )
    assert outcome["evidence"] == {
        "oru_message_id": 116,
        "oru_processing_status": "ACCEPTED",
        "delivery_id": 6,
        "delivery_status": "DELIVERED",
    }
    assert queries[0][1] == "interop-db"
    sql = queries[0][0]
    assert "o.order_status = 'FAILED'" in sql
    assert "m.message_control_id" in sql
    assert "o.result_message_control_id" in sql
    assert "m.processing_status" in sql


def test_failed_accepted_pending_result_skips_oru_and_delivers(
    monkeypatch,
):
    order = batch_order(4)
    stages = []
    state = {
        "lis_order_id": 5,
        "order_status": "FAILED",
        "result_message_control_id": (
            "SYNLIS-ORU-000005-01"
        ),
        "oru_message_id": 116,
        "oru_control_id": (
            "SYNLIS-ORU-000005-01"
        ),
        "oru_processing_status": "ACCEPTED",
        "delivery_id": 6,
        "delivery_status": "PENDING",
    }

    def unexpected_transport(*args, **kwargs):
        raise AssertionError(
            "Accepted ORU was transported again."
        )

    monkeypatch.setattr(
        synthetic_lis_batch,
        "send_order",
        unexpected_transport,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "process_order",
        unexpected_transport,
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "reconcile_accepted_result",
        lambda *args, **kwargs: {
            "status": (
                "RESULT_ACKED_AFTER_"
                "DURABLE_ACCEPTANCE"
            )
        },
    )
    monkeypatch.setattr(
        synthetic_lis_batch,
        "deliver_order",
        lambda **kwargs: (
            stages.append("deliver")
            or {"status": "DELIVERED"}
        ),
    )

    outcome = (
        synthetic_lis_batch.process_batch_order(
            order,
            oml_host="localhost",
            oml_port=6664,
            oru_host="localhost",
            oru_port=6662,
            db_container="interop-db",
            openemr_container="openemr",
            resume_state=state,
        )
    )

    assert stages == ["deliver"]
    assert outcome["status"] == "COMPLETED"
    assert outcome["lis"]["status"] == (
        "RESULT_ACKED_AFTER_DURABLE_ACCEPTANCE"
    )
    assert outcome["delivery"]["status"] == (
        "DELIVERED"
    )
    assert outcome["completed_stage"] == (
        "OPENEMR_DELIVERED"
    )
