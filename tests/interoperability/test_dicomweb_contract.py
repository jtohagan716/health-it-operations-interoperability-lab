from pathlib import Path


COMPOSE = Path("infrastructure/orthanc/compose.yaml")
CLIENT = Path("scripts/dicom/dicomweb_client.py")


def test_dicomweb_plugin_is_enabled():
    text = COMPOSE.read_text(encoding="utf-8")
    assert 'DICOM_WEB_PLUGIN_ENABLED: "true"' in text
    assert 'ORTHANC__DICOM_WEB__ENABLE: "true"' in text
    assert "ORTHANC__DICOM_WEB__ROOT: /dicom-web/" in text


def test_client_uses_real_dicomweb_protocols():
    text = CLIENT.read_text(encoding="utf-8")
    assert 'f"{self.base_url}/studies"' in text
    assert "multipart/related" in text
    assert 'type="application/dicom"' in text
    assert "application/dicom+json" in text
    assert '"instances"' in text


def test_client_reconciles_dicom_hierarchy():
    text = CLIENT.read_text(encoding="utf-8")
    for keyword in (
        "PatientID",
        "AccessionNumber",
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
    ):
        assert keyword in text
