import argparse
import json
import sys
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from pydicom import dcmread
from pydicom.dataset import Dataset


DEFAULT_BASE_URL = "http://localhost:8042/dicom-web"
DEFAULT_TIMEOUT = 30


@dataclass(frozen=True)
class DicomWebIdentity:
    patient_id: str
    accession_number: str
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str


def identity_from_dataset(dataset: Dataset) -> DicomWebIdentity:
    return DicomWebIdentity(
        patient_id=str(dataset.PatientID),
        accession_number=str(dataset.AccessionNumber),
        study_instance_uid=str(dataset.StudyInstanceUID),
        series_instance_uid=str(dataset.SeriesInstanceUID),
        sop_instance_uid=str(dataset.SOPInstanceUID),
    )


class DicomWebClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def store(self, dicom_path: str | Path) -> dict[str, Any]:
        path = Path(dicom_path)
        payload = path.read_bytes()
        boundary = "interoplab-dicomweb-boundary"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/dicom\r\n\r\n"
        ).encode("ascii") + payload + (
            f"\r\n--{boundary}--\r\n"
        ).encode("ascii")

        response = self.session.post(
            f"{self.base_url}/studies",
            data=body,
            headers={
                "Accept": "application/dicom+json",
                "Content-Type": (
                    "multipart/related; "
                    'type="application/dicom"; '
                    f"boundary={boundary}"
                ),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return {
            "status_code": response.status_code,
            "response": (
                response.json() if response.content else None
            ),
        }

    def query_studies(
        self,
        *,
        patient_id: str | None = None,
        accession_number: str | None = None,
        study_instance_uid: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {}
        if patient_id:
            params["PatientID"] = patient_id
        if accession_number:
            params["AccessionNumber"] = accession_number
        if study_instance_uid:
            params["StudyInstanceUID"] = study_instance_uid
        if limit is not None:
            params["limit"] = limit

        response = self.session.get(
            f"{self.base_url}/studies",
            params=params,
            headers={"Accept": "application/dicom+json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def retrieve_instance(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
        sop_instance_uid: str,
    ) -> bytes:
        url = "/".join(
            [
                self.base_url,
                "studies",
                quote(study_instance_uid, safe=""),
                "series",
                quote(series_instance_uid, safe=""),
                "instances",
                quote(sop_instance_uid, safe=""),
            ]
        )
        response = self.session.get(
            url,
            headers={
                "Accept": (
                    "multipart/related; "
                    'type="application/dicom"'
                )
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _dicom_part(response)


def _dicom_part(response: requests.Response) -> bytes:
    content_type = response.headers.get("Content-Type", "")
    if content_type.lower().startswith("application/dicom"):
        return response.content
    if "multipart/related" not in content_type.lower():
        raise RuntimeError(
            f"Unexpected WADO-RS Content-Type: {content_type}"
        )

    message = BytesParser(policy=default).parsebytes(
        (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("ascii")
        + response.content
    )
    for part in message.iter_parts():
        if part.get_content_type() == "application/dicom":
            payload = part.get_payload(decode=True)
            if payload:
                return payload
    raise RuntimeError("WADO-RS response contained no DICOM part.")


def dicom_json_value(item: dict[str, Any], tag: str) -> Any:
    values = item.get(tag, {}).get("Value", [])
    return values[0] if values else None


def reconcile(
    source: Dataset,
    retrieved: Dataset,
) -> dict[str, bool]:
    fields = (
        "PatientID",
        "AccessionNumber",
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
        "Modality",
    )
    return {
        field: str(getattr(source, field, ""))
        == str(getattr(retrieved, field, ""))
        for field in fields
    }


def round_trip(
    path: str | Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    source_path = Path(path)
    source = dcmread(source_path)
    identity = identity_from_dataset(source)
    client = DicomWebClient(base_url)

    store_result = client.store(source_path)
    studies = client.query_studies(
        study_instance_uid=identity.study_instance_uid
    )
    if len(studies) != 1:
        raise RuntimeError(
            "QIDO-RS did not return exactly one stored study; "
            f"found {len(studies)}."
        )

    retrieved_bytes = client.retrieve_instance(
        study_instance_uid=identity.study_instance_uid,
        series_instance_uid=identity.series_instance_uid,
        sop_instance_uid=identity.sop_instance_uid,
    )
    from io import BytesIO

    retrieved = dcmread(BytesIO(retrieved_bytes))
    checks = reconcile(source, retrieved)
    return {
        "passed": all(checks.values()),
        "store": store_result,
        "qido_match_count": len(studies),
        "identity": identity.__dict__,
        "checks": checks,
        "retrieved_byte_count": len(retrieved_bytes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise an Orthanc DICOMweb endpoint."
    )
    parser.add_argument("dicom_file", type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    result = round_trip(args.dicom_file, base_url=args.base_url)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        return 1
    print("DICOMWEB STORE QUERY RETRIEVE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
