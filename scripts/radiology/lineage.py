from __future__ import annotations

from dataclasses import dataclass

from pydicom.dataset import Dataset


@dataclass(frozen=True)
class RadiologyLineageResult:
    patient_id: str
    placer_order_number: str
    accession_number: str
    procedure_code: str
    procedure_text: str
    study_instance_uid: str
    modality: str
    report_status: str
    impression: str


def validate_order_to_dicom(
    orm: dict,
    dicom: Dataset,
) -> None:
    """
    Validate that a DICOM study belongs to the HL7 ORM
    imaging order.

    The DICOM object may be structurally valid and still
    belong to the wrong patient or order. These checks
    protect cross-system workflow identity.
    """

    if (
        orm["patient_id"]
        != str(dicom.PatientID)
    ):
        raise ValueError(
            "Radiology patient identity mismatch: "
            f"ORM patient {orm['patient_id']} "
            f"!= DICOM patient {dicom.PatientID}"
        )

    if (
        orm["accession_number"]
        != str(dicom.AccessionNumber)
    ):
        raise ValueError(
            "Radiology accession mismatch: "
            f"ORM accession "
            f"{orm['accession_number']} "
            f"!= DICOM accession "
            f"{dicom.AccessionNumber}"
        )

    if (
        orm["procedure_text"]
        != str(dicom.StudyDescription)
    ):
        raise ValueError(
            "Radiology procedure mismatch: "
            f"ORM procedure "
            f"{orm['procedure_text']} "
            f"!= DICOM study description "
            f"{dicom.StudyDescription}"
        )


def validate_order_to_oru(
    orm: dict,
    oru: dict,
) -> None:
    """
    Validate that the HL7 ORU radiology result belongs to
    the original HL7 ORM order.
    """

    if (
        orm["patient_id"]
        != oru["patient_id"]
    ):
        raise ValueError(
            "Radiology patient identity mismatch: "
            f"ORM patient {orm['patient_id']} "
            f"!= ORU patient {oru['patient_id']}"
        )

    if (
        orm["orc_placer_order_number"]
        != oru["placer_order_number"]
    ):
        raise ValueError(
            "Radiology placer-order mismatch: "
            f"ORM placer "
            f"{orm['orc_placer_order_number']} "
            f"!= ORU placer "
            f"{oru['placer_order_number']}"
        )

    if (
        orm["accession_number"]
        != oru["filler_order_number"]
    ):
        raise ValueError(
            "Radiology accession mismatch: "
            f"ORM accession "
            f"{orm['accession_number']} "
            f"!= ORU filler/accession "
            f"{oru['filler_order_number']}"
        )

    if (
        orm["procedure_code"]
        != oru["service_code"]
    ):
        raise ValueError(
            "Radiology procedure-code mismatch: "
            f"ORM procedure code "
            f"{orm['procedure_code']} "
            f"!= ORU service code "
            f"{oru['service_code']}"
        )

    if (
        orm["procedure_text"]
        != oru["service_text"]
    ):
        raise ValueError(
            "Radiology procedure-text mismatch: "
            f"ORM procedure "
            f"{orm['procedure_text']} "
            f"!= ORU service "
            f"{oru['service_text']}"
        )


def validate_result_semantics(
    oru: dict,
) -> None:
    """
    Validate expected radiology-result semantics.
    """

    if (
        oru["obr_result_status"]
        != "F"
    ):
        raise ValueError(
            "Radiology report is not final."
        )

    if (
        oru["obx_result_status"]
        != "F"
    ):
        raise ValueError(
            "Radiology observation is not final."
        )

    if (
        oru["observation_code"]
        != "IMPRESSION"
    ):
        raise ValueError(
            "Radiology impression observation "
            "is missing or unexpected."
        )

    if not oru["observation_value"]:
        raise ValueError(
            "Radiology impression text is missing."
        )


def validate_dicom_study_semantics(
    dicom: Dataset,
) -> None:
    """
    Validate DICOM attributes required by this controlled
    radiology workflow.
    """

    if not getattr(
        dicom,
        "StudyInstanceUID",
        None,
    ):
        raise ValueError(
            "DICOM StudyInstanceUID is missing."
        )

    if not getattr(
        dicom,
        "Modality",
        None,
    ):
        raise ValueError(
            "DICOM Modality is missing."
        )


def validate_full_radiology_lineage(
    orm: dict,
    dicom: Dataset,
    oru: dict,
) -> RadiologyLineageResult:
    """
    Validate the complete order -> study -> result lineage.

    Returns a normalized immutable summary when the entire
    clinical relationship is valid.
    """

    validate_order_to_dicom(
        orm,
        dicom,
    )

    validate_order_to_oru(
        orm,
        oru,
    )

    validate_result_semantics(
        oru
    )

    validate_dicom_study_semantics(
        dicom
    )

    return RadiologyLineageResult(
        patient_id=orm[
            "patient_id"
        ],
        placer_order_number=orm[
            "orc_placer_order_number"
        ],
        accession_number=orm[
            "accession_number"
        ],
        procedure_code=orm[
            "procedure_code"
        ],
        procedure_text=orm[
            "procedure_text"
        ],
        study_instance_uid=str(
            dicom.StudyInstanceUID
        ),
        modality=str(
            dicom.Modality
        ),
        report_status=oru[
            "obr_result_status"
        ],
        impression=oru[
            "observation_value"
        ],
    )