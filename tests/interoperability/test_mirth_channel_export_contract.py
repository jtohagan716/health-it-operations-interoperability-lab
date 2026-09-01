from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


CHANNEL_DIRECTORY = Path(
    "infrastructure/mirth/channels"
)

EXPECTED_CHANNELS = {
    "ADT_A04_IN.xml": {
        "name": "ADT_A04_IN",
        "port": "6661",
    },
    "ORU_R01_IN.xml": {
        "name": "ORU_R01_IN",
        "port": "6662",
    },
    "ORM_O01_IN.xml": {
        "name": "ORM_O01_IN",
        "port": "6663",
    },
}

REQUIRED_ORU_STAGES = {
    "Extract ORU Result Context",
    "Validate ORU Result Contract",
    "Persist Accepted ORU",
    "Quarantine Invalid ORU",
}


def load_channel(
    filename: str,
) -> tuple[ET.Element, str]:
    path = CHANNEL_DIRECTORY / filename

    assert path.is_file(), (
        f"Expected Mirth channel export is missing: {path}"
    )

    raw_xml = path.read_text(
        encoding="utf-8-sig"
    )

    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        pytest.fail(
            f"Invalid Mirth channel XML in {path}: {exc}"
        )

    return root, raw_xml


@pytest.mark.parametrize(
    ("filename", "expected"),
    EXPECTED_CHANNELS.items(),
)
def test_channel_export_has_expected_identity_and_port(
    filename: str,
    expected: dict[str, str],
):
    root, _ = load_channel(filename)

    channel_name = root.findtext("name")
    channel_id = root.findtext("id")
    revision = root.findtext("revision")
    ports = {
        element.text
        for element in root.iter("port")
        if element.text
    }

    assert channel_name == expected["name"]
    assert channel_id
    assert revision
    assert expected["port"] in ports


def test_channel_exports_have_unique_ids():
    channel_ids = []

    for filename in EXPECTED_CHANNELS:
        root, _ = load_channel(filename)
        channel_ids.append(root.findtext("id"))

    assert None not in channel_ids
    assert len(channel_ids) == len(set(channel_ids))


@pytest.mark.parametrize(
    "filename",
    EXPECTED_CHANNELS,
)
def test_channel_exports_use_only_inert_password_placeholders(
    filename: str,
):
    root, _ = load_channel(filename)

    passwords = [
        element.text or ""
        for element in root.iter("password")
    ]

    assert passwords, (
        f"No static password elements were found in {filename}; "
        "review the export contract before changing its "
        "credential-handling expectations."
    )

    unexpected = [
        password
        for password in passwords
        if password != "unused"
    ]

    assert unexpected == [], (
        f"{filename} contains a non-placeholder static password. "
        "Mirth channel exports must use 'unused' and obtain the "
        "runtime database credential from the environment."
    )


@pytest.mark.parametrize(
    "filename",
    EXPECTED_CHANNELS,
)
def test_database_channels_use_runtime_environment_credentials(
    filename: str,
):
    _, raw_xml = load_channel(filename)

    assert "INTEROP_DB_USER" in raw_xml
    assert "INTEROP_DB_PASSWORD" in raw_xml
    assert (
        "jdbc:postgresql://interop-db:5432/interop"
        in raw_xml
    )


def test_oru_channel_contains_required_processing_stages():
    root, _ = load_channel("ORU_R01_IN.xml")

    stage_names = {
        element.text
        for element in root.iter("name")
        if element.text
    }

    missing_stages = (
        REQUIRED_ORU_STAGES
        - stage_names
    )

    assert missing_stages == set(), (
        "ORU channel export is missing required processing "
        f"stages: {sorted(missing_stages)}"
    )
