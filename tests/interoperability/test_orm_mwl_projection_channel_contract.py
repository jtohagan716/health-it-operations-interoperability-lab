from html import unescape
from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHANNEL_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "channels"
    / "ORM_O01_IN.xml"
)


def channel_text() -> str:
    return unescape(
        CHANNEL_PATH.read_text(
            encoding="utf-8"
        )
    )


def normalized_channel_text() -> str:
    return " ".join(
        channel_text().split()
    ).lower()


def test_channel_export_remains_well_formed_xml():
    ElementTree.parse(CHANNEL_PATH)


def test_validated_patient_demographics_enter_mwl_context():
    text = channel_text()

    expected_mappings = {
        "mwl_patient_family_name": "familyName",
        "mwl_patient_given_name": "givenName",
        "mwl_patient_date_of_birth": "dateOfBirth",
        "mwl_patient_administrative_sex":
            "administrativeSex",
    }

    for map_key, source_variable in (
        expected_mappings.items()
    ):
        assert f'"{map_key}"' in text
        assert source_variable in text


def test_xrch2_has_explicit_dicom_scheduling_mapping():
    text = channel_text()

    for expected in (
        '"XRCH2"',
        '"DX"',
        '"XRAY_MODALITY"',
        '"ORDER_DATETIME"',
    ):
        assert expected in text

    assert "Unsupported MWL procedure mapping" in text


def test_order_datetime_fallback_is_explicit_and_deterministic():
    text = channel_text()

    assert "mwl_scheduled_start_date" in text
    assert "mwl_scheduled_start_time" in text
    assert "mwl_schedule_source" in text

    assert "substring(0, 8)" in text
    assert "substring(8, 14)" in text

    assert (
        "ORC-9 order datetime fallback"
        in text
    )


def test_scheduled_procedure_step_identity_is_bounded():
    text = channel_text()

    assert (
        "mwl_scheduled_procedure_step_id"
        in text
    )

    assert (
        "accessionNumber.length > 16"
        in text
    )

    assert (
        "MWL scheduled procedure step ID"
        in text
    )


def test_destination_persists_pending_projection():
    text = normalized_channel_text()

    assert (
        "insert into "
        "audit.modality_worklist_items"
        in text
    )

    for field in (
        "orm_order_id",
        "patient_identifier",
        "patient_family_name",
        "patient_given_name",
        "patient_date_of_birth",
        "patient_administrative_sex",
        "accession_number",
        "requested_procedure_id",
        "procedure_code",
        "procedure_description",
        "modality",
        "scheduled_station_ae_title",
        "scheduled_start_date",
        "scheduled_start_time",
        "schedule_source",
        "scheduled_procedure_step_id",
    ):
        assert field in text

    assert (
        "on conflict (orm_order_id) "
        "do nothing"
        in text
    )


def test_projection_is_derived_from_canonical_orm_order():
    text = normalized_channel_text()

    assert "from audit.orm_orders" in text
    assert (
        "where transaction_id = "
        "cast(? as bigint)"
        in text
    )

    assert "accession_number" in text
    assert "placer_order_number" in text
    assert "procedure_code" in text


def test_exact_replay_verifies_existing_projection():
    text = channel_text()

    assert "verifyProjectionSql" in text
    assert "MWL projection row was not found" in text

    for field in (
        "patient_identifier",
        "accession_number",
        "requested_procedure_id",
        "procedure_code",
        "modality",
        "scheduled_station_ae_title",
        "scheduled_start_date",
        "scheduled_start_time",
        "schedule_source",
        "scheduled_procedure_step_id",
        "projection_status",
    ):
        assert f'"{field}"' in text

    assert (
        '"PENDING"'
        in text
    )


def test_conflicting_reuse_exits_before_projection():
    text = channel_text()

    conflict_guard = text.index(
        'auditOutcome == "CONFLICTING_REUSE"'
    )

    projection_insert = text.index(
        "INSERT INTO "
        "audit.modality_worklist_items"
    )

    assert conflict_guard < projection_insert