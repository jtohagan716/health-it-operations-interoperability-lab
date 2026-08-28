from __future__ import annotations

from pathlib import Path
from secrets import token_hex

import pydicom
from pydicom.uid import generate_uid

from scripts.incidents.adapters.dicom import (
    send_dicom_file,
)
from scripts.incidents.adapters.hl7 import (
    send_hl7_file,
)
from scripts.incidents.models import (
    IncidentCase,
    IncidentState,
)
from scripts.incidents.scenario import IncidentScenario


ORM_TEMPLATE = Path(
    "fixtures/radiology/orm-rad-workflow-000001.hl7"
)

DICOM_TEMPLATE = Path(
    "fixtures/radiology/dicom-rad-workflow-000001.dcm"
)

INCIDENT_ROOT = Path(
    "artifacts/incidents/INC-RAD-001"
)


class RadiologyAccessionMismatchScenario(
    IncidentScenario
):
    """
    Controlled radiology troubleshooting scenario.

    The upstream HL7 order is valid and independently
    accepted, and a DICOM study is independently valid
    and storable.

    The operator must investigate whether the clinical
    identity remains consistent across the workflow.
    """

    def create_case(self) -> IncidentCase:
        suffix = token_hex(3).upper()

        case_key = f"RADINC{suffix}"

        workspace = (
            INCIDENT_ROOT / case_key
        )

        return IncidentCase(
            incident_id="INC-RAD-001",
            scenario_id=(
                "radiology-accession-correlation"
            ),
            title=(
                "Imaging Study Not Found "
                "as Expected"
            ),
            protocols=("HL7v2", "DICOM"),
            symptom=(
                "The radiology order was accepted, "
                "but the expected imaging study "
                "cannot be located using the "
                "expected order information."
            ),
            case_key=case_key,
            workspace=workspace,
        )

    def prepare(
        self,
        case: IncidentCase,
    ) -> None:
        case.workspace.mkdir(
            parents=True,
            exist_ok=False,
        )

        patient_id = case.case_key

        message_control_id = (
            f"RAD-ORM-{case.case_key}"
        )

        placer_order = (
            f"ORD{case.case_key}"
        )

        expected_accession = (
            f"ACC{case.case_key}"
        )

        observed_dicom_accession = (
            f"IMG{case.case_key}"
        )

        orm_output = (
            case.workspace / "order.hl7"
        )

        dicom_output = (
            case.workspace / "study.dcm"
        )

        self._prepare_orm(
            output_path=orm_output,
            message_control_id=message_control_id,
            patient_id=patient_id,
            placer_order=placer_order,
            accession=expected_accession,
        )

        study_uid = self._prepare_dicom(
            output_path=dicom_output,
            patient_id=patient_id,
            accession=observed_dicom_accession,
        )

        case.metadata.update(
            {
                "message_control_id": (
                    message_control_id
                ),
                "patient_id": patient_id,
                "placer_order": placer_order,
                "expected_accession": (
                    expected_accession
                ),
                "study_instance_uid": study_uid,
            }
        )

        case.register_artifact(
            orm_output,
            "HL7_ORM",
            "Incident-owned radiology order",
        )

        case.register_artifact(
            dicom_output,
            "DICOM",
            "Incident-owned imaging study",
        )

        case.register_owned_resource(
            "LOCAL_WORKSPACE",
            str(case.workspace),
        )

        case.set_state(
            IncidentState.PREPARED
        )

    def activate(
        self,
        case: IncidentCase,
    ) -> None:
        if case.state != IncidentState.PREPARED:
            raise RuntimeError(
                "Incident must be PREPARED "
                "before activation."
            )

        orm_path = (
            case.workspace / "order.hl7"
        )

        dicom_path = (
            case.workspace / "study.dcm"
        )

        hl7_result = send_hl7_file(
            orm_path,
            host="127.0.0.1",
            port=6663,
            timeout=30.0,
        )

        if not hl7_result.accepted:
            raise RuntimeError(
                "ORM was not accepted. "
                f"ACK code: {hl7_result.ack_code}"
            )

        if not hl7_result.control_id_matches:
            raise RuntimeError(
                "ORM ACK control-ID correlation "
                "failed."
            )

        case.metadata.update(
            {
                "hl7_ack_code": (
                    hl7_result.ack_code
                ),
                "hl7_ack_control_id": (
                    hl7_result.ack_control_id
                ),
                "hl7_round_trip_ms": (
                    hl7_result.round_trip_ms
                ),
            }
        )

        case.register_owned_resource(
            "HL7_TRANSACTION",
            hl7_result.message_control_id,
            ack_code=hl7_result.ack_code,
        )

        dicom_result = send_dicom_file(
            dicom_path,
            host="127.0.0.1",
            port=4242,
            calling_ae_title="INTEROPLAB",
            called_ae_title="ORTHANC",
        )

        if not dicom_result.stored_successfully:
            raise RuntimeError(
                "DICOM C-STORE failed. "
                f"Status: "
                f"0x{dicom_result.status_code:04X}"
            )

        case.metadata.update(
            {
                "dicom_status_code": (
                    dicom_result.status_code
                ),
                "dicom_round_trip_ms": (
                    dicom_result.round_trip_ms
                ),
            }
        )

        case.register_owned_resource(
            "ORTHANC_STUDY",
            dicom_result.study_instance_uid,
            patient_id=dicom_result.patient_id,
        )

        case.set_state(
            IncidentState.ACTIVE
        )

    def cleanup(
        self,
        case: IncidentCase,
    ) -> None:
        raise NotImplementedError(
            "Automated cleanup is intentionally disabled "
            "until ownership-safe deletion is implemented."
        )

    @staticmethod
    def _prepare_orm(
        *,
        output_path: Path,
        message_control_id: str,
        patient_id: str,
        placer_order: str,
        accession: str,
    ) -> None:
        message = ORM_TEMPLATE.read_text(
            encoding="utf-8"
        )

        replacements = {
            "RAD-ORM-WORKFLOW-000001": (
                message_control_id
            ),
            "RADPAT000001": patient_id,
            "RADORD000001": placer_order,
            "RAD000001": accession,
        }

        for old, new in replacements.items():
            if old not in message:
                raise RuntimeError(
                    "Expected ORM template value "
                    f"not found: {old}"
                )

            message = message.replace(
                old,
                new,
            )

        output_path.write_text(
            message,
            encoding="utf-8",
        )

    @staticmethod
    def _prepare_dicom(
        *,
        output_path: Path,
        patient_id: str,
        accession: str,
    ) -> str:
        dataset = pydicom.dcmread(
            DICOM_TEMPLATE
        )

        study_uid = generate_uid()
        series_uid = generate_uid()
        sop_uid = generate_uid()

        dataset.PatientID = patient_id
        dataset.AccessionNumber = accession

        dataset.StudyInstanceUID = (
            study_uid
        )

        dataset.SeriesInstanceUID = (
            series_uid
        )

        dataset.SOPInstanceUID = (
            sop_uid
        )

        dataset.file_meta.MediaStorageSOPInstanceUID = (
            sop_uid
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        dataset.save_as(
            output_path,
            enforce_file_format=True,
        )

        return study_uid
