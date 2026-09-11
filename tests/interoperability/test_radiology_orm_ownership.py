from __future__ import annotations

import pytest

import scripts.radiology.persist_lineage as persistence


EXPECTED = {
    "patient_identifier": "RADPAT000001",
    "placer_order_number": "RADORD000001",
    "accession_number": "RAD000001",
    "procedure_code": "XRCH2",
}


def test_missing_persisted_orm_owner_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        persistence,
        "run_interop_db_sql",
        lambda sql: "",
    )

    owner = persistence.find_persisted_orm_owner(
        accession_number="RAD000001",
    )

    assert owner is None


def test_matching_persisted_orm_owner_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        persistence,
        "run_interop_db_sql",
        lambda sql: (
            "41|RADPAT000001|RADORD000001|"
            "RAD000001|XRCH2"
        ),
    )

    owner = persistence.find_persisted_orm_owner(
        accession_number="RAD000001",
    )

    assert owner is not None

    persistence.assert_orm_owner_matches_expected(
        owner,
        EXPECTED,
    )


def test_conflicting_persisted_orm_patient_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        persistence,
        "run_interop_db_sql",
        lambda sql: (
            "1|LAB000001|RADORD000001|"
            "RAD000001|XRCH2"
        ),
    )

    owner = persistence.find_persisted_orm_owner(
        accession_number="RAD000001",
    )

    assert owner is not None

    with pytest.raises(
        RuntimeError,
        match=(
            "Persisted ORM order ownership conflict.*"
            "patient_identifier"
        ),
    ):
        persistence.assert_orm_owner_matches_expected(
            owner,
            EXPECTED,
        )
def test_multiple_consistent_orm_rows_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        persistence,
        "run_interop_db_sql",
        lambda sql: (
            "41|RADPAT000001|RADORD000001|"
            "RAD000001|XRCH2\n"
            "42|RADPAT000001|RADORD000001|"
            "RAD000001|XRCH2"
        ),
    )

    owner = persistence.find_persisted_orm_owner(
        accession_number="RAD000001",
    )

    assert owner is not None
    assert owner["orm_order_id"] == "42"

    persistence.assert_orm_owner_matches_expected(
        owner,
        EXPECTED,
    )

def test_multiple_persisted_orm_owners_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        persistence,
        "run_interop_db_sql",
        lambda sql: (
            "1|PATIENT1|ORDER1|RAD000001|XRCH2\n"
            "2|PATIENT2|ORDER2|RAD000001|XRCH2"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="accession ownership is ambiguous",
    ):
        persistence.find_persisted_orm_owner(
            accession_number="RAD000001",
        )