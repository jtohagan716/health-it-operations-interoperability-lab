import json
import subprocess
import sys
from pathlib import Path


COMPOSE_PATH = Path(
    "infrastructure/orthanc/compose.yaml"
)
ORTHANC_CONFIG_PATH = Path(
    "infrastructure/orthanc/orthanc.json"
)
DOCKERFILE_PATH = Path(
    "infrastructure/orthanc/storage-scp.Dockerfile"
)
REQUIREMENTS_PATH = Path(
    "infrastructure/orthanc/"
    "storage-scp-requirements.txt"
)
SCP_PATH = Path(
    "scripts/dicom/storage_scp.py"
)
HEALTH_PATH = Path(
    "scripts/dicom/storage_scp_health.py"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_compose_manages_storage_scp_lifecycle():
    text = read(COMPOSE_PATH)

    assert "dicom-storage-scp:" in text
    assert "storage-scp.Dockerfile" in text
    assert "restart: unless-stopped" in text
    assert '"11112:11112"' in text
    assert "DICOM_SCP_AE_TITLE: INTEROPLAB" in text
    assert "DICOM_SCP_OUTPUT_DIR: /data/received" in text


def test_compose_uses_dicom_health_not_tcp_only():
    text = read(COMPOSE_PATH)

    assert "healthcheck:" in text
    assert "scripts.dicom.storage_scp_health" in text
    assert "--called-ae" in text
    assert "INTEROPLAB" in text
    assert "condition: service_healthy" in text


def test_received_objects_are_visible_on_host():
    text = read(COMPOSE_PATH)

    assert (
        "../../artifacts/dicom/received:"
        "/data/received"
    ) in text


def test_orthanc_uses_compose_service_discovery():
    config = json.loads(
        read(ORTHANC_CONFIG_PATH)
    )

    interoplab = config["DicomModalities"]["interoplab"]
    unavailable = config["DicomModalities"]["unavailable"]

    assert interoplab == [
        "INTEROPLAB",
        "dicom-storage-scp",
        11112,
    ]

    assert unavailable == [
        "UNAVAILABLE",
        "host.docker.internal",
        11113,
    ]


def test_receiver_dependencies_are_pinned():
    requirements = {
        line.strip()
        for line in read(REQUIREMENTS_PATH).splitlines()
        if line.strip()
    }

    assert requirements == {
        "pydicom==3.0.2",
        "pynetdicom==3.0.4",
    }

    dockerfile = read(DOCKERFILE_PATH)
    assert "--requirement /tmp/requirements.txt" in dockerfile
    assert (
        'CMD ["python", "-m", '
        '"scripts.dicom.storage_scp"]'
    ) in dockerfile


def test_receiver_exposes_operational_configuration():
    text = read(SCP_PATH)

    for setting in (
        "DICOM_SCP_AE_TITLE",
        "DICOM_SCP_HOST",
        "DICOM_SCP_PORT",
        "DICOM_SCP_OUTPUT_DIR",
    ):
        assert setting in text

    assert "SecondaryCaptureImageStorage" in text
    assert "Verification" in text
    assert "EVT_C_STORE" in text
    assert "0xC210" in text
    assert "0xA700" in text


def test_health_probe_requires_successful_c_echo():
    text = read(HEALTH_PATH)

    assert "Verification" in text
    assert "send_c_echo" in text
    assert "status_code != 0x0000" in text
    assert "return 1" in text


def test_receiver_help_returns_without_starting_server():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.dicom.storage_scp",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert completed.returncode == 0
    assert "usage:" in completed.stdout.lower()
    assert "Waiting for incoming" not in completed.stdout
