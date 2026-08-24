from pathlib import Path

from scripts.hl7.analyze_orm import (
    analyze_orm,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_ORM_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "hl7"
    / "orm"
    / "orm-o01-rad000001.hl7"
)


def replace_segment_field(
    message: str,
    segment_name: str,
    field_number: int,
    value: str,
) -> str:
    """
    Replace one HL7 field in the first matching segment.

    HL7 field numbering matches the split representation used by
    the lab analyzers:

        ORC-2 -> index 2
        OBR-3 -> index 3
    """

    lines = message.splitlines()

    for index, line in enumerate(lines):
        if not line.startswith(
            segment_name + "|"
        ):
            continue

        fields = line.split("|")

        if field_number >= len(fields):
            raise AssertionError(
                f"{segment_name}-{field_number} "
                "does not exist in fixture."
            )

        fields[field_number] = value

        lines[index] = "|".join(
            fields
        )

        return "\n".join(lines) + "\n"

    raise AssertionError(
        f"Segment {segment_name} not found."
    )


def write_modified_fixture(
    tmp_path: Path,
    filename: str,
    message: str,
) -> Path:
    fixture = (
        tmp_path
        / filename
    )

    fixture.write_text(
        message,
        encoding="utf-8",
    )

    return fixture


def test_valid_orm_o01_preserves_imaging_order_contract():
    """
    The controlled HL7 ORM^O01 General Order Message must
    preserve the expected patient and radiology-order identity.
    """

    result = analyze_orm(
        VALID_ORM_FIXTURE
    )

    assert all(
        result["checks"].values()
    )

    assert (
        result["message_code"]
        == "ORM"
    )

    assert (
        result["trigger_event"]
        == "O01"
    )

    assert (
        result["message_structure"]
        == "ORM_O01"
    )

    assert (
        result["patient_id"]
        == "LAB000001"
    )

    assert (
        result["visit_number"]
        == "VISIT000004"
    )

    assert (
        result["order_control"]
        == "NW"
    )

    assert (
        result["orc_placer_order_number"]
        == "RADORD000001"
    )

    assert (
        result["obr_placer_order_number"]
        == "RADORD000001"
    )

    assert (
        result["orc_filler_order_number"]
        == "RAD000001"
    )

    assert (
        result["obr_filler_order_number"]
        == "RAD000001"
    )

    assert (
        result["accession_number"]
        == "RAD000001"
    )

    assert (
        result["procedure_code"]
        == "XRCH2"
    )

    assert (
        result["procedure_text"]
        == "Chest X-ray 2 Views"
    )

    assert (
        result["procedure_coding_system"]
        == "99INTEROP"
    )

    assert (
        result["ordering_provider_id"]
        == "54321"
    )

    assert (
        result["ordering_provider_family"]
        == "Carter"
    )

    assert (
        result["ordering_provider_given"]
        == "Elena"
    )


def test_orm_o01_detects_placer_order_identity_mismatch(
    tmp_path: Path,
):
    """
    ORC and OBR are describing the same imaging order.

    If their placer order numbers disagree, the interface
    contract must identify the inconsistency.
    """

    message = VALID_ORM_FIXTURE.read_text(
        encoding="utf-8"
    )

    conflicting_message = replace_segment_field(
        message,
        "OBR",
        2,
        "RADORD999999",
    )

    fixture = write_modified_fixture(
        tmp_path,
        "orm-o01-placer-mismatch.hl7",
        conflicting_message,
    )

    result = analyze_orm(
        fixture
    )

    assert (
        result["orc_placer_order_number"]
        == "RADORD000001"
    )

    assert (
        result["obr_placer_order_number"]
        == "RADORD999999"
    )

    assert (
        result["checks"][
            "ORC and OBR placer order numbers agree"
        ]
        is False
    )

    assert not all(
        result["checks"].values()
    )


def test_orm_o01_detects_accession_identity_mismatch(
    tmp_path: Path,
):
    """
    In this lab contract, the radiology-side filler identifier
    is used as the accession identifier that will later be
    correlated to DICOM AccessionNumber.

    ORC and OBR disagreement must therefore be treated as an
    imaging-order identity failure.
    """

    message = VALID_ORM_FIXTURE.read_text(
        encoding="utf-8"
    )

    conflicting_message = replace_segment_field(
        message,
        "OBR",
        3,
        "RAD999999",
    )

    fixture = write_modified_fixture(
        tmp_path,
        "orm-o01-accession-mismatch.hl7",
        conflicting_message,
    )

    result = analyze_orm(
        fixture
    )

    assert (
        result["orc_filler_order_number"]
        == "RAD000001"
    )

    assert (
        result["obr_filler_order_number"]
        == "RAD999999"
    )

    assert (
        result["accession_number"]
        == "RAD999999"
    )

    assert (
        result["checks"][
            "ORC and OBR filler order numbers agree"
        ]
        is False
    )

    assert not all(
        result["checks"].values()
    )