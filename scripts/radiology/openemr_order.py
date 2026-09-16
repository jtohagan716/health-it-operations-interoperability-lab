from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


RADIOLOGY_PROVIDER_ID = 1
RADIOLOGY_PROVIDER_NAME = "Interop Radiology"
APPROVED_PROCEDURE_CODE = "XRCH2"
APPROVED_PROCEDURE_TEXT = "Chest X-ray 2 Views"
LOCAL_TIME_ZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class OpenEMRRadiologyOrder:
    openemr_order_id: int
    order_uuid_hex: str
    placer_order_number: str
    accession_number: str
    message_control_id: str
    patient_id: int
    patient_identifier: str
    patient_given_name: str
    patient_family_name: str
    patient_date_of_birth: str
    patient_sex: str
    encounter_id: int
    visit_number: str
    ordering_provider_id: int
    ordering_provider_given_name: str
    ordering_provider_family_name: str
    ordered_at: str
    clinical_history: str
    procedure_code: str
    procedure_text: str


def _require(
    source: dict[str, Any],
    field: str,
) -> Any:
    value = source.get(field)

    if value is None or value == "":
        raise ValueError(
            f"OpenEMR radiology order is missing {field}."
        )

    return value


def _identifier(
    prefix: str,
    order_id: int,
) -> str:
    return f"{prefix}{order_id:08d}"


def _hl7_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=LOCAL_TIME_ZONE
        )
    else:
        parsed = parsed.astimezone(
            LOCAL_TIME_ZONE
        )

    return parsed.strftime("%Y%m%d%H%M%S%z")


def normalize_openemr_order(
    source: dict[str, Any],
) -> OpenEMRRadiologyOrder:
    """Validate one UI-created OpenEMR imaging order."""

    order_id = int(
        _require(source, "procedure_order_id")
    )

    if order_id <= 0:
        raise ValueError(
            "OpenEMR order ID must be positive."
        )

    if int(source.get("activity", 0)) != 1:
        raise ValueError(
            "OpenEMR radiology order is not active."
        )

    if (
        int(source.get("lab_id", 0))
        != RADIOLOGY_PROVIDER_ID
        or source.get("radiology_provider")
        != RADIOLOGY_PROVIDER_NAME
    ):
        raise ValueError(
            "Order must target Interop Radiology."
        )

    if (
        source.get("procedure_code")
        != APPROVED_PROCEDURE_CODE
    ):
        raise ValueError(
            "Order procedure must be XRCH2."
        )

    if (
        source.get("procedure_name")
        != APPROVED_PROCEDURE_TEXT
    ):
        raise ValueError(
            "Order procedure text must be "
            "Chest X-ray 2 Views."
        )

    if int(
        source.get("procedure_order_seq", 0)
    ) != 1:
        raise ValueError(
            "Order must contain exactly the approved "
            "first procedure line."
        )

    if source.get("procedure_order_type") != "procedure":
        raise ValueError(
            "OpenEMR order type must be procedure."
        )

    if source.get("procedure_type") != "procedure":
        raise ValueError(
            "OpenEMR order-line type must be procedure."
        )

    patient_identifier = str(
        _require(source, "patient_identifier")
    )

    if not patient_identifier.startswith("SYNTHMRN"):
        raise ValueError(
            "Only SYNTHMRN synthetic patients are allowed."
        )

    return OpenEMRRadiologyOrder(
        openemr_order_id=order_id,
        order_uuid_hex=str(
            _require(source, "order_uuid_hex")
        ),
        placer_order_number=_identifier(
            "OEMRRAD",
            order_id,
        ),
        accession_number=_identifier(
            "RAD",
            order_id,
        ),
        message_control_id=_identifier(
            "OEMR-RAD-",
            order_id,
        ),
        patient_id=int(
            _require(source, "patient_id")
        ),
        patient_identifier=patient_identifier,
        patient_given_name=str(
            _require(source, "patient_given_name")
        ),
        patient_family_name=str(
            _require(source, "patient_family_name")
        ),
        patient_date_of_birth=str(
            _require(source, "patient_date_of_birth")
        ),
        patient_sex=str(
            _require(source, "patient_sex")
        ),
        encounter_id=int(
            _require(source, "encounter_id")
        ),
        visit_number=str(
            _require(source, "encounter_id")
        ),
        ordering_provider_id=int(
            _require(source, "provider_id")
        ),
        ordering_provider_given_name=str(
            _require(source, "provider_given_name")
        ),
        ordering_provider_family_name=str(
            _require(source, "provider_family_name")
        ),
        ordered_at=str(
            _require(source, "date_ordered")
        ),
        clinical_history=str(
            _require(source, "clinical_hx")
        ),
        procedure_code=str(
            _require(source, "procedure_code")
        ),
        procedure_text=str(
            _require(source, "procedure_name")
        ),
    )


def build_orm_segments(
    order: OpenEMRRadiologyOrder,
) -> list[str]:
    """Build the controlled ORM for one verified order."""

    timestamp = _hl7_timestamp(order.ordered_at)
    provider = "^".join(
        [
            str(order.ordering_provider_id),
            order.ordering_provider_family_name,
            order.ordering_provider_given_name,
        ]
    )

    msh = "|".join(
        [
            "MSH",
            "^~\\&",
            "OPENEMR",
            "INTEROPLAB",
            "MIRTH",
            "INTEROPLAB",
            timestamp,
            "",
            "ORM^O01^ORM_O01",
            order.message_control_id,
            "P",
            "2.5.1",
        ]
    )

    pid = "|".join(
        [
            "PID",
            "1",
            "",
            (
                f"{order.patient_identifier}"
                "^^^INTEROPLAB^MR"
            ),
            "",
            (
                f"{order.patient_family_name}^"
                f"{order.patient_given_name}^^^^^L"
            ),
            "",
            order.patient_date_of_birth,
            order.patient_sex,
        ]
    )

    pv1_fields = [
        "PV1",
        "1",
        "O",
        "RADIOLOGY^XRAY^1^INTEROPLAB",
        "",
        "",
        "",
        provider,
    ]
    pv1_fields.extend([""] * 11)
    pv1_fields.append(order.visit_number)
    pv1 = "|".join(pv1_fields)

    orc = "|".join(
        [
            "ORC",
            "NW",
            order.placer_order_number,
            order.accession_number,
            "",
            "SC",
            "",
            "",
            "",
            timestamp,
            "",
            "",
            provider,
        ]
    )

    obr = "|".join(
        [
            "OBR",
            "1",
            order.placer_order_number,
            order.accession_number,
            (
                f"{order.procedure_code}^"
                f"{order.procedure_text}^99INTEROP"
            ),
        ]
    )

    return [msh, pid, pv1, orc, obr]
