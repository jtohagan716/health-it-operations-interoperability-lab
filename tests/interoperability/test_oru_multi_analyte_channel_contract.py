from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHANNEL_PATH = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / "channels"
    / "ORU_R01_IN.xml"
)


def channel_text() -> str:
    return CHANNEL_PATH.read_text(encoding="utf-8")


def test_source_extracts_every_obx_into_ordered_collection():
    text = channel_text()

    assert "for each (var obxSegment in msg[&apos;OBX&apos;])" in text
    assert "observationSequence++" in text
    assert "oru_observations_json" in text
    assert "JSON.stringify(observations)" in text
    assert "oru_observation_count" in text


def test_observation_collection_preserves_wire_and_semantic_fields():
    text = channel_text()

    for field in (
        "obx_set_id",
        "value_type",
        "code",
        "text",
        "coding_system",
        "value",
        "units",
        "reference_range",
        "abnormal_flag",
        "result_status",
    ):
        assert f"{field}:" in text


def test_validation_iterates_and_locations_each_observation():
    text = channel_text()

    assert "observationIndex &lt; observations.length" in text
    assert "At least one OBX observation present" in text
    assert "OBX[&quot;" in text
    assert "Numeric OBX contains numeric value" in text
    assert "OBR and OBX result status agree" in text


def test_synthetic_panel_has_explicit_membership_policy():
    text = channel_text()

    assert "SYN-CHEM-4" in text
    for code in ("2345-7", "3094-0", "2160-0", "2951-2"):
        assert f"&quot;{code}&quot;: true" in text
    assert "OBX belongs to SYN-CHEM-4 panel" in text
    assert "SYN-CHEM-4 required member present" in text
    assert "Panel observation code is unique" in text


def test_legacy_single_analyte_profile_retains_code_equality():
    text = channel_text()

    assert "else if (serviceCode != observation.code)" in text
    assert "OBR and OBX observation codes agree" in text


def test_writer_persists_result_group_before_observations():
    text = channel_text()

    group_position = text.index("INSERT INTO audit.oru_result_groups")
    observation_position = text.index(
        "INSERT INTO audit.oru_observations",
        group_position,
    )

    assert group_position < observation_position
    assert "oru_result_group_id" in text[group_position:]
    assert "result_group_sequence" in text[group_position:]


def test_writer_persists_every_observation_with_sequence_and_set_id():
    text = channel_text()

    assert "persistedIndex &lt; persistedObservations.length" in text
    assert "persistedObservation.sequence" in text
    assert "persistedObservation.obx_set_id" in text
    assert "oru_persisted_observation_count" in text


def test_panel_persistence_is_transactional_and_rolls_back_on_error():
    text = channel_text()

    assert "dbConn.setAutoCommit(false)" in text
    assert "dbConn.commit()" in text
    assert "dbConn.rollback()" in text
    assert "catch (persistenceError)" in text
    assert "throw persistenceError" in text


def test_exact_replay_commits_without_duplicate_semantic_rows():
    text = channel_text()

    assert "ORU exact replay reused canonical semantic record" in text
    replay_position = text.index(
        "ORU exact replay reused canonical semantic record"
    )
    following_text = text[replay_position:]
    assert following_text.index("dbConn.commit()") < following_text.index(
        "return;"
    )
