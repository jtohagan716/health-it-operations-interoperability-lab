from types import SimpleNamespace

import pytest

from scripts.hl7 import scenario_runtime


BASE_SEGMENTS = [
    (
        "MSH|^~\\&|LABSYSTEM|INTEROPLAB|MIRTH|"
        "INTEROPLAB|20260820153000-0400||"
        "ORU^R01^ORU_R01|CONTROL-ORIGINAL|P|2.5.1"
    ),
    "PID|1||LAB000001^^^INTEROPLAB^MR||Testpatient^Avery",
    (
        "OBX|1|NM|2345-7^Glucose^LN||105|"
        "mg/dL|70-99|H|||F"
    ),
    (
        "OBX|2|NM|2823-3^Potassium^LN||4.2|"
        "mmol/L|3.5-5.1|N|||F"
    ),
]


def test_generate_control_id_preserves_prefix_and_is_unique():
    first = scenario_runtime.generate_control_id(
        "LAB-ORU"
    )
    second = scenario_runtime.generate_control_id(
        "LAB-ORU"
    )

    assert first.startswith("LAB-ORU-")
    assert len(first.rsplit("-", 1)[1]) == 12
    assert first != second


@pytest.mark.parametrize(
    ("prefix", "suffix_length"),
    [
        ("", 12),
        ("   ", 12),
        ("LAB-ORU", 0),
        ("LAB-ORU", -1),
    ],
)
def test_generate_control_id_rejects_invalid_arguments(
    prefix: str,
    suffix_length: int,
):
    with pytest.raises(ValueError):
        scenario_runtime.generate_control_id(
            prefix,
            suffix_length=suffix_length,
        )


def test_replace_message_control_id_does_not_mutate_source():
    updated = scenario_runtime.replace_message_control_id(
        BASE_SEGMENTS,
        "CONTROL-REPLACEMENT",
    )

    assert "CONTROL-REPLACEMENT" in updated[0]
    assert "CONTROL-ORIGINAL" in BASE_SEGMENTS[0]
    assert updated is not BASE_SEGMENTS


def test_replace_observation_value_supports_occurrence():
    updated = scenario_runtime.replace_observation_value(
        BASE_SEGMENTS,
        "4.8",
        occurrence=1,
    )

    assert "|105|" in updated[2]
    assert "|4.8|" in updated[3]
    assert "|4.2|" in BASE_SEGMENTS[3]


def test_replace_segment_field_rejects_missing_segment():
    with pytest.raises(
        ValueError,
        match="OBR occurrence 0 was not found",
    ):
        scenario_runtime.replace_segment_field(
            BASE_SEGMENTS,
            segment_name="OBR",
            field_index=4,
            new_value="2345-7",
        )


def test_replace_segment_field_rejects_missing_field():
    with pytest.raises(
        ValueError,
        match="field index 20",
    ):
        scenario_runtime.replace_segment_field(
            BASE_SEGMENTS,
            segment_name="PID",
            field_index=20,
            new_value="value",
        )


def test_send_segments_returns_structured_ack(monkeypatch):
    response = (
        b"\x0bMSH|^~\\&|MIRTH|INTEROPLAB|LABSYSTEM|"
        b"INTEROPLAB|20260901120000||ACK^R01^ACK|"
        b"ACK-1|P|2.5.1\r"
        b"MSA|AA|CONTROL-ORIGINAL|Message accepted.\r"
        b"\x1c\x0d"
    )

    monkeypatch.setattr(
        scenario_runtime,
        "send_mllp_frame",
        lambda *args, **kwargs: response,
    )

    ack = scenario_runtime.send_segments(
        BASE_SEGMENTS,
        host="localhost",
        port=6662,
    )

    assert ack.code == "AA"
    assert ack.control_id == "CONTROL-ORIGINAL"
    assert ack.accepted is True
    assert "Message accepted." in ack.text
    assert ack.round_trip_seconds >= 0


def test_send_segments_rejects_uncorrelated_ack(monkeypatch):
    response = (
        b"\x0bMSH|^~\\&|MIRTH|INTEROPLAB|LABSYSTEM|"
        b"INTEROPLAB|20260901120000||ACK^R01^ACK|"
        b"ACK-2|P|2.5.1\r"
        b"MSA|AA|WRONG-CONTROL-ID\r"
        b"\x1c\x0d"
    )

    monkeypatch.setattr(
        scenario_runtime,
        "send_mllp_frame",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(
        RuntimeError,
        match="ACK correlation failed",
    ):
        scenario_runtime.send_segments(
            BASE_SEGMENTS,
            host="localhost",
            port=6662,
        )


def test_run_psql_returns_trimmed_output(monkeypatch):
    completed = SimpleNamespace(
        returncode=0,
        stdout="accepted|1\n",
        stderr="",
    )

    monkeypatch.setattr(
        scenario_runtime.subprocess,
        "run",
        lambda *args, **kwargs: completed,
    )

    output = scenario_runtime.run_psql(
        "SELECT 'accepted', 1;"
    )

    assert output == "accepted|1"


def test_run_psql_raises_actionable_error(monkeypatch):
    completed = SimpleNamespace(
        returncode=1,
        stdout="",
        stderr="connection failed",
    )

    monkeypatch.setattr(
        scenario_runtime.subprocess,
        "run",
        lambda *args, **kwargs: completed,
    )

    with pytest.raises(
        RuntimeError,
        match="connection failed",
    ):
        scenario_runtime.run_psql("SELECT 1;")
