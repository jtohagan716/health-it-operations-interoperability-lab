from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = PROJECT_ROOT / "fixtures" / "synthetic" / "patient-demographics-profile.json"
DEFAULT_RECEIVER = Path(__file__).with_name("openemr_patient_receiver.php")
DEFAULT_CONTAINER = "health-it-openemr-lab-openemr-1"
APPROVED_ENVIRONMENT = "local-lab"
PAYLOAD_PLACEHOLDER = "__SYNTH_PATIENT_PAYLOAD_BASE64__"
ALLOWED_RACES = {
    "white", "black_or_afri_amer", "Asian", "amer_ind_or_alaska_native",
    "native_hawai_or_pac_island", "decline_to_specify",
}
ALLOWED_ETHNICITIES = {"not_hisp_or_latin", "hisp_or_latin", "decline_to_specify"}
ALLOWED_LANGUAGES = {"English", "Spanish", "french", "arabic", "chinese"}
ALLOWED_MARITAL_STATUSES = {
    "single", "married", "divorced", "widowed", "separated", "domestic partner",
}


class PatientDemographicsError(RuntimeError):
    """Raised when the synthetic patient contract cannot be satisfied."""


def load_profile(path: Path = DEFAULT_PROFILE) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    validate_profile(profile)
    return profile


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("environment") != APPROVED_ENVIRONMENT:
        raise PatientDemographicsError("Profile environment must be local-lab.")
    if profile.get("synthetic_only") is not True:
        raise PatientDemographicsError("Profile must declare synthetic_only=true.")
    if profile.get("source_system") != "SYNTHETIC_POPULATION_V1":
        raise PatientDemographicsError("Unexpected source system.")
    if profile.get("patient_count") != 100:
        raise PatientDemographicsError("Approved patient count is exactly 100.")
    if profile.get("provider_count") != 25:
        raise PatientDemographicsError("Approved provider count is exactly 25.")
    if profile.get("patient_identifier_prefix") != "SYNTHMRN":
        raise PatientDemographicsError("Unexpected patient identifier namespace.")
    if profile.get("assigning_authority") != "INTEROPLAB":
        raise PatientDemographicsError("Unexpected assigning authority.")
    if len(profile.get("cohorts", [])) != 10:
        raise PatientDemographicsError("Exactly ten cohorts are required.")
    if not set(profile.get("race_distribution", [])) <= ALLOWED_RACES:
        raise PatientDemographicsError("Profile contains an unsupported OpenEMR race option.")
    if not set(profile.get("ethnicity_distribution", [])) <= ALLOWED_ETHNICITIES:
        raise PatientDemographicsError("Profile contains an unsupported OpenEMR ethnicity option.")
    if not set(profile.get("language_distribution", [])) <= ALLOWED_LANGUAGES:
        raise PatientDemographicsError("Profile contains an unsupported OpenEMR language option.")
    if not set(profile.get("marital_distribution", [])) <= ALLOWED_MARITAL_STATUSES:
        raise PatientDemographicsError("Profile contains an unsupported OpenEMR marital option.")


def birth_date_for(sequence: int, cohort: str) -> str:
    if cohort == "PEDIATRIC":
        year = 2012 + ((sequence * 3) % 14)
    elif cohort in {"OLDER_ADULT", "CARDIOVASCULAR"}:
        year = 1938 + ((sequence * 5) % 22)
    else:
        year = 1965 + ((sequence * 7) % 40)

    if cohort == "IDENTITY_EDGE":
        pair = (sequence - 1) // 20
        year = 1975 + pair
        month = 1 + (pair % 12)
        day = 10 + pair
    else:
        month = 1 + ((sequence * 5) % 12)
        day = 1 + ((sequence * 11) % 27)
    return f"{year:04d}-{month:02d}-{day:02d}"


def patient_name(sequence: int, cohort: str) -> tuple[str, str]:
    if cohort == "IDENTITY_EDGE":
        pair = (sequence - 1) // 20 + 1
        return f"IdentityTwin{pair:02d}", f"SyntheticEdge{pair:02d}"
    return f"Synthetic{sequence:03d}", f"Patient{sequence:03d}"


def build_patients(profile: dict[str, Any]) -> list[dict[str, Any]]:
    patients: list[dict[str, Any]] = []
    for sequence in range(1, profile["patient_count"] + 1):
        cohort = profile["cohorts"][(sequence - 1) % len(profile["cohorts"])]
        given_name, family_name = patient_name(sequence, cohort)
        phone_suffix = 99 + sequence
        patients.append(
            {
                "patient_id": f"SYNTHMRN{sequence:06d}",
                "logical_key": f"patient:SYNTHMRN{sequence:06d}",
                "assigning_authority": profile["assigning_authority"],
                "identifier_type": profile["identifier_type"],
                "given_name": given_name,
                "middle_name": "Test",
                "family_name": family_name,
                "name_type": "L",
                "birth_date": birth_date_for(sequence, cohort),
                "administrative_sex": "Male" if sequence % 2 else "Female",
                "street": f"{1000 + sequence} Synthetic Patient Road",
                "city": "Testville",
                "state": "NY",
                "postal_code": f"{sequence:05d}",
                "country_code": "US",
                "phone": f"716-555-{phone_suffix:04d}",
                "email": f"synthpatient{sequence:06d}@example.invalid",
                "race": profile["race_distribution"][(sequence - 1) % len(profile["race_distribution"])],
                "ethnicity": profile["ethnicity_distribution"][(sequence - 1) % len(profile["ethnicity_distribution"])],
                "language": profile["language_distribution"][(sequence - 1) % len(profile["language_distribution"])],
                "marital_status": profile["marital_distribution"][(sequence - 1) % len(profile["marital_distribution"])],
                "provider_id": f"SYNPROV{((sequence - 1) % profile['provider_count']) + 1:04d}",
                "provider_username": f"synprov{((sequence - 1) % profile['provider_count']) + 1:04d}",
                "golden_patient": sequence <= 10,
                "cohort_codes": [cohort],
            }
        )
    validate_patients(patients, profile)
    return patients


def validate_patients(patients: list[dict[str, Any]], profile: dict[str, Any]) -> None:
    if len(patients) != 100:
        raise PatientDemographicsError("Generated patient count must equal 100.")
    if len({patient["patient_id"] for patient in patients}) != 100:
        raise PatientDemographicsError("Patient identifiers must be unique.")
    if len({patient["email"] for patient in patients}) != 100:
        raise PatientDemographicsError("Patient emails must be unique.")
    if sum(patient["golden_patient"] for patient in patients) != 10:
        raise PatientDemographicsError("Exactly ten golden patients are required.")
    for patient in patients:
        if not patient["patient_id"].startswith("SYNTHMRN"):
            raise PatientDemographicsError("Patient outside synthetic identifier namespace.")
        if not patient["email"].endswith("@example.invalid"):
            raise PatientDemographicsError("Patient email must use example.invalid.")
        if not patient["phone"].startswith("716-555-01"):
            raise PatientDemographicsError("Patient phone must use the reserved 555-0100 through 0199 range.")
        if patient["birth_date"] >= profile["reference_date"]:
            raise PatientDemographicsError("Patient birth date must precede the reference date.")


def build_manifest(profile: dict[str, Any], patients: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "profile_version": profile["profile_version"],
        "issue": profile["issue"],
        "seed": profile["seed"],
        "run_id": profile["run_id"],
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": profile["environment"],
        "synthetic_only": profile["synthetic_only"],
        "source_system": profile["source_system"],
        "assigning_authority": profile["assigning_authority"],
        "identifier_type": profile["identifier_type"],
        "patients": patients,
    }


def select_probe(manifest: dict[str, Any]) -> dict[str, Any]:
    probe = dict(manifest)
    probe["patients"] = [manifest["patients"][0]]
    probe["probe"] = True
    return probe


def validate_commit_confirmation(args: argparse.Namespace, manifest: dict[str, Any]) -> None:
    expected = len(manifest["patients"])
    if args.environment != APPROVED_ENVIRONMENT:
        raise PatientDemographicsError("--environment must equal local-lab.")
    if args.confirm_patient_count != expected:
        raise PatientDemographicsError(
            f"--confirm-patient-count must equal {expected} for this operation."
        )


def invoke_receiver(
    manifest: dict[str, Any],
    action: str,
    container: str,
    receiver_path: Path = DEFAULT_RECEIVER,
) -> dict[str, Any]:
    payload = dict(manifest)
    payload["action"] = action
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    template = receiver_path.read_text(encoding="utf-8")
    if PAYLOAD_PLACEHOLDER not in template:
        raise PatientDemographicsError("Patient receiver payload placeholder is missing.")
    rendered = template.replace(PAYLOAD_PLACEHOLDER, encoded)

    result = subprocess.run(
        ["docker", "exec", "-i", "--user", "apache", container, "php"],
        input=rendered.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        raise PatientDemographicsError(
            f"OpenEMR patient receiver failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PatientDemographicsError(
            f"Patient receiver did not return JSON.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        ) from exc
    if response.get("status") not in {"PASS", "VERIFIED"}:
        raise PatientDemographicsError(json.dumps(response, indent=2))
    return response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision deterministic synthetic OpenEMR patients.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--environment")
    parser.add_argument("--confirm-patient-count", type=int)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = load_profile(args.profile)
        manifest = build_manifest(profile, build_patients(profile))
        if args.probe:
            manifest = select_probe(manifest)
        if args.verify:
            print(json.dumps(invoke_receiver(manifest, "verify", args.container), indent=2))
            return 0
        if not args.commit:
            print("SYNTHETIC PATIENT DEMOGRAPHICS: DRY RUN")
            print(json.dumps(manifest, indent=2))
            return 0
        validate_commit_confirmation(args, manifest)
        print(json.dumps(invoke_receiver(manifest, "commit", args.container), indent=2))
        return 0
    except (PatientDemographicsError, OSError, KeyError, ValueError) as exc:
        print(f"SYNTHETIC PATIENT DEMOGRAPHICS: FAIL - {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
