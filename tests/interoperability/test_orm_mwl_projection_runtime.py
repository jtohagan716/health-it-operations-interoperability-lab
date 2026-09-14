from test_orm_o01_audit_persistence import (
    create_unique_orm_message,
    query_logical_transaction,
    query_receipt_attempts,
    run_psql,
    send_orm,
)


def query_projection(
    transaction_id: int,
) -> dict[str, str | int]:
    rows = run_psql(
        f"""
SELECT
    m.orm_order_id,
    m.patient_identifier,
    m.patient_family_name,
    m.patient_given_name,
    m.patient_date_of_birth,
    m.patient_administrative_sex,
    m.accession_number,
    m.requested_procedure_id,
    m.procedure_code,
    m.procedure_description,
    m.modality,
    m.scheduled_station_ae_title,
    m.scheduled_start_date,
    m.scheduled_start_time,
    m.schedule_source,
    m.scheduled_procedure_step_id,
    m.projection_status,
    m.projection_attempt_count,
    COALESCE(m.study_instance_uid, ''),
    COALESCE(m.orthanc_worklist_id, '')
FROM audit.modality_worklist_items m
JOIN audit.orm_orders o
    ON o.orm_order_id = m.orm_order_id
WHERE o.transaction_id = {transaction_id};
""".strip()
    )

    assert len(rows) == 1, (
        "Expected exactly one MWL projection for "
        f"transaction {transaction_id}; found "
        f"{len(rows)}: {rows}"
    )

    fields = rows[0].split("|")

    assert len(fields) == 20, (
        f"Unexpected MWL projection row: {rows[0]}"
    )

    return {
        "orm_order_id": int(fields[0]),
        "patient_identifier": fields[1],
        "patient_family_name": fields[2],
        "patient_given_name": fields[3],
        "patient_date_of_birth": fields[4],
        "patient_administrative_sex": fields[5],
        "accession_number": fields[6],
        "requested_procedure_id": fields[7],
        "procedure_code": fields[8],
        "procedure_description": fields[9],
        "modality": fields[10],
        "scheduled_station_ae_title": fields[11],
        "scheduled_start_date": fields[12],
        "scheduled_start_time": fields[13],
        "schedule_source": fields[14],
        "scheduled_procedure_step_id": fields[15],
        "projection_status": fields[16],
        "projection_attempt_count": int(fields[17]),
        "study_instance_uid": fields[18],
        "orthanc_worklist_id": fields[19],
    }


def query_projection_count(
    transaction_id: int,
) -> int:
    rows = run_psql(
        f"""
SELECT COUNT(*)
FROM audit.modality_worklist_items m
JOIN audit.orm_orders o
    ON o.orm_order_id = m.orm_order_id
WHERE o.transaction_id = {transaction_id};
""".strip()
    )

    assert len(rows) == 1
    return int(rows[0])


def delete_projection(
    transaction_id: int,
) -> None:
    run_psql(
        f"""
DELETE FROM audit.modality_worklist_items
WHERE orm_order_id = (
    SELECT orm_order_id
    FROM audit.orm_orders
    WHERE transaction_id = {transaction_id}
);
""".strip()
    )


def expected_projection(
    segments: list[str],
    expected_order: dict[str, str],
    orm_order_id: int,
) -> dict[str, str | int]:
    pid_fields = next(
        segment
        for segment in segments
        if segment.startswith("PID|")
    ).split("|")

    orc_fields = next(
        segment
        for segment in segments
        if segment.startswith("ORC|")
    ).split("|")

    patient_name = pid_fields[5].split("^")
    order_datetime = orc_fields[9]

    return {
        "orm_order_id": orm_order_id,
        "patient_identifier":
            expected_order["patient_identifier"],
        "patient_family_name": patient_name[0],
        "patient_given_name": patient_name[1],
        "patient_date_of_birth": pid_fields[7],
        "patient_administrative_sex": pid_fields[8],
        "accession_number":
            expected_order["accession_number"],
        "requested_procedure_id":
            expected_order["placer_order_number"],
        "procedure_code":
            expected_order["procedure_code"],
        "procedure_description":
            expected_order["procedure_text"],
        "modality": "DX",
        "scheduled_station_ae_title":
            "XRAY_MODALITY",
        "scheduled_start_date":
            order_datetime[0:8],
        "scheduled_start_time":
            order_datetime[8:14],
        "schedule_source": "ORDER_DATETIME",
        "scheduled_procedure_step_id":
            expected_order["accession_number"],
        "projection_status": "PENDING",
        "projection_attempt_count": 0,
        "study_instance_uid": "",
        "orthanc_worklist_id": "",
    }


def test_orm_creates_replays_and_repairs_one_mwl_projection():
    segments, expected_order = (
        create_unique_orm_message(
            "RAD-ORM-MWL"
        )
    )

    first_ack_code, first_ack_control_id = (
        send_orm(segments)
    )

    assert first_ack_code == "AA"
    assert (
        first_ack_control_id
        == expected_order["message_control_id"]
    )

    transaction = query_logical_transaction(
        expected_order
    )
    transaction_id = transaction["transaction_id"]

    first_projection = query_projection(
        transaction_id
    )

    expected = expected_projection(
        segments,
        expected_order,
        first_projection["orm_order_id"],
    )

    assert first_projection == expected
    assert query_projection_count(transaction_id) == 1

    replay_ack_code, replay_ack_control_id = (
        send_orm(segments)
    )

    assert replay_ack_code == "AA"
    assert (
        replay_ack_control_id
        == expected_order["message_control_id"]
    )

    assert query_projection_count(transaction_id) == 1
    assert query_projection(transaction_id) == expected

    delete_projection(transaction_id)

    assert query_projection_count(transaction_id) == 0

    repair_ack_code, repair_ack_control_id = (
        send_orm(segments)
    )

    assert repair_ack_code == "AA"
    assert (
        repair_ack_control_id
        == expected_order["message_control_id"]
    )

    assert query_projection_count(transaction_id) == 1
    assert query_projection(transaction_id) == expected

    conflicting_segments = segments.copy()

    pid_index = next(
        index
        for index, segment in enumerate(
            conflicting_segments
        )
        if segment.startswith("PID|")
    )

    pid_fields = conflicting_segments[
        pid_index
    ].split("|")

    pid_fields[3] = (
        "MWLWRONGPATIENT^^^INTEROPLAB^MR"
    )

    conflicting_segments[pid_index] = "|".join(
        pid_fields
    )

    conflict_ack_code, conflict_ack_control_id = (
        send_orm(conflicting_segments)
    )

    assert conflict_ack_code == "AR"
    assert (
        conflict_ack_control_id
        == expected_order["message_control_id"]
    )

    final_transaction = query_logical_transaction(
        expected_order
    )

    assert (
        final_transaction["transaction_id"]
        == transaction_id
    )
    assert final_transaction["receipt_count"] == 4

    attempts = query_receipt_attempts(
        expected_order
    )

    assert [
        attempt["attempt_outcome"]
        for attempt in attempts
    ] == [
        "FIRST_DELIVERY",
        "EXACT_REPLAY",
        "EXACT_REPLAY",
        "CONFLICTING_REUSE",
    ]

    assert query_projection_count(transaction_id) == 1
    assert query_projection(transaction_id) == expected

    print()
    print("ORM TO MWL PROJECTION: PASS")
    print(
        "Message control ID: "
        + expected_order["message_control_id"]
    )
    print(f"Transaction ID: {transaction_id}")
    print(
        "ORM order ID: "
        + str(first_projection["orm_order_id"])
    )
    print(
        "Accession: "
        + expected_order["accession_number"]
    )
    print("Projection count: 1")
    print("Receipt attempts: 4")
    print("Final status: PENDING")