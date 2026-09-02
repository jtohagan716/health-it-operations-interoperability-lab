import json
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROFILE_PATH = (
    PROJECT_ROOT
    / "fixtures"
    / "synthetic"
    / "population-profile.json"
)

MANIFEST_SCHEMA_PATH = (
    PROJECT_ROOT
    / "fixtures"
    / "synthetic"
    / "manifest.schema.json"
)

DOCUMENT_PATHS = [
    PROJECT_ROOT
    / "docs"
    / "test-data"
    / "synthetic-population-requirements.md",
    PROJECT_ROOT
    / "docs"
    / "test-data"
    / "synthetic-data-dictionary.md",
    PROJECT_ROOT
    / "docs"
    / "test-data"
    / "synthetic-clinical-scenarios.md",
    PROJECT_ROOT
    / "docs"
    / "test-data"
    / "synthetic-population-validation-plan.md",
]

EXPECTED_TARGETS = {
    "organizations": 1,
    "facilities": 3,
    "departments": 8,
    "providers": 25,
    "patients": 100,
    "golden_patients": 10,
    "historical_encounters": 300,
    "vital_sign_panels": 600,
    "diagnoses": 400,
    "medications": 200,
    "allergies": 100,
    "immunizations": 200,
    "lab_orders": 450,
    "lab_results": 500,
    "radiology_orders": 100,
    "radiology_reports": 100,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_documents_exist_and_reference_issue_31():
    for path in DOCUMENT_PATHS:
        assert path.is_file(), f"Missing contract document: {path}"

        text = path.read_text(encoding="utf-8")

        assert "#31" in text, (
            f"Contract document does not reference issue #31: {path}"
        )


def test_population_profile_matches_approved_targets():
    profile = load_json(PROFILE_PATH)

    assert profile["issue"] == 31
    assert profile["profile_version"] == "1.0.0"
    assert profile["seed"] == 20260902
    assert profile["targets"] == EXPECTED_TARGETS


def test_population_profile_is_synthetic_and_local_only():
    profile = load_json(PROFILE_PATH)
    safety = profile["safety"]

    assert profile["environment"] == "local-lab"
    assert profile["synthetic_only"] is True
    assert profile["source_system"] == "SYNTHETIC_POPULATION_V1"

    assert safety["dry_run_default"] is True
    assert safety["commit_flag_required"] is True
    assert safety["patient_count_confirmation_required"] is True
    assert safety["allow_real_npi"] is False
    assert safety["allow_production_data"] is False


def test_approved_endpoints_are_loopback_only():
    profile = load_json(PROFILE_PATH)

    for base_url in profile["approved_base_urls"]:
        parsed = urlparse(base_url)

        assert parsed.scheme in {"http", "https"}
        assert parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def test_patient_safety_limit_equals_approved_target():
    profile = load_json(PROFILE_PATH)

    assert (
        profile["safety"]["maximum_patients"]
        == profile["targets"]["patients"]
        == 100
    )


def test_identifier_templates_use_reserved_synthetic_prefixes():
    profile = load_json(PROFILE_PATH)
    templates = profile["identifier_templates"]

    assert templates["patient"].startswith("SYNTHMRN")
    assert templates["provider"].startswith("SYNPROV")
    assert templates["encounter"].startswith("SYNENC")
    assert templates["message_control"].startswith("SYNTH-")


def test_declared_facility_and_department_counts_match_targets():
    profile = load_json(PROFILE_PATH)

    assert (
        len(profile["facility_codes"])
        == profile["targets"]["facilities"]
    )
    assert (
        len(profile["department_codes"])
        == profile["targets"]["departments"]
    )
    assert len(set(profile["facility_codes"])) == len(
        profile["facility_codes"]
    )
    assert len(set(profile["department_codes"])) == len(
        profile["department_codes"]
    )


def test_manifest_schema_enforces_local_synthetic_provenance():
    schema = load_json(MANIFEST_SCHEMA_PATH)

    required = set(schema["required"])

    assert {
        "run_id",
        "profile_version",
        "seed",
        "environment",
        "synthetic_only",
        "generated_at",
        "source_system",
        "expected_counts",
        "outcomes",
    }.issubset(required)

    properties = schema["properties"]

    assert properties["environment"]["const"] == "local-lab"
    assert properties["synthetic_only"]["const"] is True
    assert (
        properties["source_system"]["const"]
        == "SYNTHETIC_POPULATION_V1"
    )
    assert properties["run_id"]["pattern"].startswith("^SYNTH-")
