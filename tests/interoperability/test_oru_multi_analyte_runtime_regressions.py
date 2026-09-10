from pathlib import Path


CHANNEL_PATH = Path(
    "infrastructure/mirth/channels/ORU_R01_IN.xml"
)


def channel_text() -> str:
    return CHANNEL_PATH.read_text(encoding="utf-8")


def test_operator_trace_uses_collected_observation_status():
    text = channel_text()

    assert "obxResultStatus" not in text
    assert (
        "firstObservation.result_status"
        in text
    )


def test_observation_sequence_is_explicitly_cast_to_integer():
    text = channel_text()

    assert (
        ") VALUES (?, ?, CAST(? AS INTEGER), "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    ) in text
