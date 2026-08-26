from pathlib import Path

from scripts.hl7.analyze_dorn_order import (
    analyze_dorn_order,
    get_diagnosis_associations,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DORN_CROSS_ASSOCIATION_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "hl7"
    / "dorn"
    / "dorn-oml-o21-dg1-cross-association.hl7"
)

DORN_EXPECTED_ASSOCIATION_FIXTURE = (
    PROJECT_ROOT
    / "fixtures"
    / "hl7"
    / "dorn"
    / "dorn-oml-o21-dg1-association-expected.hl7"
)


def test_dorn_multi_test_order_exposes_diagnosis_cross_association():
    """
    Controlled source data assigns:

        DORNTESTA -> ICD10:E11.9
        DORNTESTB -> ICD10:I10

    This runtime-generated OpenEMR fixture demonstrates that
    both diagnoses are emitted beneath both OBR groups.

    The test passes when the known interoperability defect is
    detected deterministically.
    """

    result = analyze_dorn_order(
        DORN_CROSS_ASSOCIATION_FIXTURE
    )

    associations = get_diagnosis_associations(
        result
    )

    expected = [
        {
            "procedure_code": "DORNTESTA",
            "diagnosis_codes": ["E11.9"],
        },
        {
            "procedure_code": "DORNTESTB",
            "diagnosis_codes": ["I10"],
        },
    ]

    assert associations != expected

    assert associations == [
        {
            "procedure_code": "DORNTESTA",
            "diagnosis_codes": [
                "E11.9",
                "I10",
            ],
        },
        {
            "procedure_code": "DORNTESTB",
            "diagnosis_codes": [
                "E11.9",
                "I10",
            ],
        },
    ]


def test_dorn_dg1_diagnosis_type_contains_coding_system_value():
    """
    DG1-6 is the HL7 Diagnosis Type field.

    The captured OpenEMR DORN message places the source coding
    system value ICD10 into DG1-6 for every diagnosis.
    """

    result = analyze_dorn_order(
        DORN_CROSS_ASSOCIATION_FIXTURE
    )

    diagnosis_types = [
        diagnosis["diagnosis_type"]
        for group in result[
            "order_groups"
        ]
        for diagnosis in group[
            "diagnoses"
        ]
    ]

    assert diagnosis_types == [
        "ICD10",
        "ICD10",
        "ICD10",
        "ICD10",
    ]

    recognized_diagnosis_types = {
        "A",
        "W",
        "F",
    }

    assert all(
        diagnosis_type
        not in recognized_diagnosis_types
        for diagnosis_type
        in diagnosis_types
    )


def test_dorn_dg1_exposes_diagnosis_components():
    """
    Preserve the actual DG1 components emitted by OpenEMR so
    later regression work can distinguish association defects
    from coding-system or description defects.
    """

    result = analyze_dorn_order(
        DORN_CROSS_ASSOCIATION_FIXTURE
    )

    first_group = result[
        "order_groups"
    ][0]

    first_diagnosis = first_group[
        "diagnoses"
    ][0]

    assert (
        first_diagnosis["code"]
        == "E11.9"
    )

    assert (
        first_diagnosis["description"]
        == "Type 2 diabetes mellitus without complications"
    )

    assert (
        first_diagnosis["coding_system"]
        == "I10c"
    )

    assert (
        first_diagnosis["diagnosis_type"]
        == "ICD10"
    )


def test_dorn_expected_fixture_preserves_per_obr_diagnosis_association():
    """
    Positive control for the OBR-to-DG1 association contract.

    This fixture intentionally changes only diagnosis grouping.
    Other DORN field semantics are preserved from the captured
    runtime message so they can be tested independently.
    """

    result = analyze_dorn_order(
        DORN_EXPECTED_ASSOCIATION_FIXTURE
    )

    associations = get_diagnosis_associations(
        result
    )

    assert associations == [
        {
            "procedure_code": "DORNTESTA",
            "diagnosis_codes": ["E11.9"],
        },
        {
            "procedure_code": "DORNTESTB",
            "diagnosis_codes": ["I10"],
        },
    ]
