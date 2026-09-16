import pytest

from scripts.radiology.openemr_order import (
    build_orm_segments,
    normalize_openemr_order,
)


def source_record() -> dict:
    return {
        "procedure_order_id": 107,
        "order_uuid_hex": (
            "A2C0F0A5A2FB4801BCDFB412E30ECA1C"
        ),
        "external_id": None,
        "patient_id": 6,
        "patient_identifier": "SYNTHMRN000005",
        "patient_given_name": "Synthetic005",
        "patient_family_name": "Patient005",
        "patient_date_of_birth": "20000202",
        "patient_sex": "M",
        "encounter_id": 122,
        "encounter_time": "20250916140000",
        "encounter_reason": (
            "Respiratory symptom follow-up - "
            "longitudinal review"
        ),
        "provider_id": 12,
        "provider_given_name": "Provider005",
        "provider_family_name": "Synthetic",
        "lab_id": 1,
        "radiology_provider": "Interop Radiology",
        "date_ordered": "2026-09-15 00:00:00",
        "clinical_hx": "Persistent cough",
        "activity": 1,
        "procedure_order_type": "procedure",
        "date_transmitted": None,
        "procedure_order_seq": 1,
        "procedure_code": "XRCH2",
        "procedure_name": "Chest X-ray 2 Views",
        "procedure_type": "procedure",
    }


def test_openemr_order_maps_to_radiology_identity():
    order = normalize_openemr_order(
        source_record()
    )

    assert order.openemr_order_id == 107
    assert order.placer_order_number == (
        "OEMRRAD00000107"
    )
    assert order.accession_number == "RAD00000107"
    assert order.message_control_id == (
        "OEMR-RAD-00000107"
    )
    assert order.patient_identifier == (
        "SYNTHMRN000005"
    )
    assert order.visit_number == "122"
    assert order.procedure_code == "XRCH2"
    assert order.procedure_text == (
        "Chest X-ray 2 Views"
    )
    assert order.clinical_history == (
        "Persistent cough"
    )


def test_openemr_order_builds_expected_orm():
    order = normalize_openemr_order(
        source_record()
    )

    segments = build_orm_segments(order)

    assert len(segments) == 5
    assert (
        "ORM^O01^ORM_O01"
        in segments[0]
    )
    assert (
        "SYNTHMRN000005^^^INTEROPLAB^MR"
        in segments[1]
    )
    assert segments[2].endswith("|122")
    assert (
        "ORC|NW|OEMRRAD00000107|RAD00000107"
        in segments[3]
    )
    assert segments[4] == (
        "OBR|1|OEMRRAD00000107|RAD00000107|"
        "XRCH2^Chest X-ray 2 Views^99INTEROP"
    )


def test_nonradiology_provider_is_rejected():
    source = source_record()
    source["lab_id"] = 4
    source["radiology_provider"] = (
        "Synthetic Interoperability Laboratory"
    )

    with pytest.raises(
        ValueError,
        match="Interop Radiology",
    ):
        normalize_openemr_order(source)


def test_unapproved_procedure_is_rejected():
    source = source_record()
    source["procedure_code"] = "UNKNOWN"

    with pytest.raises(
        ValueError,
        match="XRCH2",
    ):
        normalize_openemr_order(source)
