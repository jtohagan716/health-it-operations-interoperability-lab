import json
from pathlib import Path


REPOSITORY_ROOT = (
    Path(__file__).resolve().parents[2]
)

ORTHANC_DIRECTORY = (
    REPOSITORY_ROOT
    / "infrastructure"
    / "orthanc"
)

DOCKERFILE = (
    ORTHANC_DIRECTORY
    / "orthanc.Dockerfile"
)

COMPOSE_FILE = (
    ORTHANC_DIRECTORY
    / "compose.yaml"
)

ORTHANC_CONFIG = (
    ORTHANC_DIRECTORY
    / "orthanc.json"
)

ORTHANC_DIGEST = (
    "sha256:"
    "ffdfa1141b6b89a631c10d5ac612e18b"
    "934d601c3501e73b597bd700ecfd4004"
)

WORKLISTS_SHA256 = (
    "9bcfcd01bf889a95f740afd0452e6893"
    "67d6ec10e9c3ca2a9e9c1ecb4d8b7960"
)


def test_mwl_image_inputs_are_pinned():
    dockerfile = DOCKERFILE.read_text(
        encoding="utf-8"
    )

    assert (
        f"orthancteam/orthanc@{ORTHANC_DIGEST}"
        in dockerfile
    )

    assert (
        "WORKLISTS_PLUGIN_VERSION=0.9.2"
        in dockerfile
    )

    assert (
        f"--checksum=sha256:{WORKLISTS_SHA256}"
        in dockerfile
    )

    assert (
        "chmod 0555 "
        "/usr/share/orthanc/plugins/"
        "libOrthancWorklists.so"
        in dockerfile
    )


def test_compose_builds_the_mwl_image():
    compose = COMPOSE_FILE.read_text(
        encoding="utf-8"
    )

    assert (
        "dockerfile: "
        "infrastructure/orthanc/"
        "orthanc.Dockerfile"
        in compose
    )

    assert (
        "image: health-it-orthanc-mwl:"
        "1.13.0-worklists-0.9.2"
        in compose
    )

    assert (
        "image: orthancteam/orthanc:latest"
        not in compose
    )


def test_orthanc_enables_database_backed_worklists():
    configuration = json.loads(
        ORTHANC_CONFIG.read_text(
            encoding="utf-8"
        )
    )

    worklists = configuration[
        "Worklists"
    ]

    assert worklists["Enable"] is True

    assert (
        worklists["SaveInOrthancDatabase"]
        is True
    )

    assert (
        worklists["SetStudyInstanceUidIfMissing"]
        is True
    )

    assert (
        worklists["DeleteWorklistsOnStableStudy"]
        is False
    )

    assert (
        worklists["DeleteWorklistsDelay"]
        == 0
    )


def test_ct_modality_is_authorized_for_mwl_queries():
    configuration = json.loads(
        ORTHANC_CONFIG.read_text(
            encoding="utf-8"
        )
    )

    ct_modality = configuration[
        "DicomModalities"
    ]["ct_modality"]

    assert ct_modality == [
        "CT_MODALITY",
        "host.docker.internal",
        11114,
    ]


def test_xray_modality_is_authorized_for_mwl_queries():
    configuration = json.loads(
        ORTHANC_CONFIG.read_text(
            encoding="utf-8"
        )
    )

    xray_modality = configuration[
        "DicomModalities"
    ]["xray_modality"]

    assert xray_modality == [
        "XRAY_MODALITY",
        "host.docker.internal",
        11115,
    ]