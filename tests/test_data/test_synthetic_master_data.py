import argparse
import json
from pathlib import Path

import pytest

from scripts.synthetic.master_data import (
    APPROVED_ENVIRONMENT,
    DEFAULT_PROFILE,
    MasterDataError,
    build_master_data,
    load_profile,
    select_probe,
    validate_commit_confirmation,
)


def test_profile_generates_exact_master_data_counts():
    data = build_master_data(load_profile())

    assert len(data["facilities"]) == 3
    assert len(data["departments"]) == 8
    assert len(data["providers"]) == 25


def test_provider_identity_is_unique_and_deterministic():
    first = build_master_data(load_profile())
    second = build_master_data(load_profile())

    assert first == second

    providers = first["providers"]
    assert len({p["provider_id"] for p in providers}) == 25
    assert len({p["username"] for p in providers}) == 25
    assert len({p["email"] for p in providers}) == 25
    assert providers[0]["provider_id"] == "SYNPROV0001"
    assert providers[-1]["provider_id"] == "SYNPROV0025"


def test_no_master_record_declares_an_npi():
    data = build_master_data(load_profile())

    assert all("facility_npi" not in item for item in data["facilities"])
    assert all("npi" not in item for item in data["providers"])


def test_all_emails_use_reserved_invalid_domain():
    data = build_master_data(load_profile())

    emails = [item["email"] for item in data["facilities"]]
    emails += [item["email"] for item in data["providers"]]

    assert all(email.endswith("@example.invalid") for email in emails)


def test_provider_relationships_resolve():
    data = build_master_data(load_profile())
    facility_codes = {item["facility_code"] for item in data["facilities"]}
    department_codes = {item["code"] for item in data["departments"]}

    assert all(p["facility_code"] in facility_codes for p in data["providers"])
    assert all(p["department_code"] in department_codes for p in data["providers"])


def test_specialties_have_distinct_expected_taxonomies():
    data = build_master_data(load_profile())
    actual = {provider["specialty"]: provider["taxonomy"] for provider in data["providers"]}

    assert actual == {
        "Family Medicine": "207Q00000X",
        "Emergency Medicine": "207P00000X",
        "Internal Medicine": "207R00000X",
        "Laboratory Medicine": "207ZP0105X",
        "Diagnostic Radiology": "2085R0202X",
        "Medication Management": "208U00000X",
        "Pediatrics": "208000000X",
        "Specialty Care": "174400000X",
    }


def test_probe_contains_one_real_fixture_pair():
    data = build_master_data(load_profile())
    probe = select_probe(data)

    assert probe["probe"] is True
    assert len(probe["facilities"]) == 1
    assert len(probe["providers"]) == 1
    assert probe["providers"][0]["facility_code"] == probe["facilities"][0]["facility_code"]


def test_full_commit_requires_exact_confirmation():
    data = build_master_data(load_profile())
    args = argparse.Namespace(
        environment=APPROVED_ENVIRONMENT,
        confirm_provider_count=25,
        confirm_facility_count=3,
    )

    validate_commit_confirmation(args, data)


@pytest.mark.parametrize(
    ("environment", "providers", "facilities"),
    [
        (None, 25, 3),
        ("production", 25, 3),
        (APPROVED_ENVIRONMENT, None, 3),
        (APPROVED_ENVIRONMENT, 24, 3),
        (APPROVED_ENVIRONMENT, 25, None),
        (APPROVED_ENVIRONMENT, 25, 2),
    ],
)
def test_commit_rejects_missing_or_incorrect_confirmation(
    environment,
    providers,
    facilities,
):
    data = build_master_data(load_profile())
    args = argparse.Namespace(
        environment=environment,
        confirm_provider_count=providers,
        confirm_facility_count=facilities,
    )

    with pytest.raises(MasterDataError):
        validate_commit_confirmation(args, data)


def test_profile_rejects_a_real_npi_field(tmp_path: Path):
    profile = load_profile()
    profile["facilities"][0]["facility_npi"] = "1234567890"
    path = tmp_path / "unsafe-profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(MasterDataError):
        load_profile(path)


def test_openemr_receiver_contains_required_guards():
    receiver = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "synthetic"
        / "openemr_master_data_receiver.php"
    ).read_text(encoding="utf-8")

    assert "local-lab" in receiver
    assert "SYNTHETIC_POPULATION_V1" in receiver
    assert "$_GET['site'] = 'default';" in receiver
    assert "ini_set('display_errors', '0');" in receiver
    assert "START TRANSACTION" in receiver
    assert receiver.index("$verification = verifyPayload($payload)") < receiver.index("sqlStatement('COMMIT')")
    assert "ROLLBACK" in receiver
    assert "users_facility" in receiver
    assert "Synthetic provider must not declare an NPI" in receiver
    assert "Existing provider taxonomy cannot be safely normalized" in receiver
    assert "SYNTHETIC_POPULATION_V1|" in receiver
