"""Guarded deterministic condition provisioning for the local OpenEMR lab."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ROOT / "fixtures" / "synthetic" / "diagnosis-profile.json"
DEFAULT_RECEIVER = Path(__file__).with_name("openemr_diagnosis_receiver.php")
DEFAULT_CONTAINER = "health-it-openemr-lab-openemr-1"


def load_profile(path: Path = DEFAULT_PROFILE) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("synthetic_only") is not True:
        raise ValueError("Profile must declare synthetic_only=true.")
    if profile.get("environment") != "local-lab":
        raise ValueError("Profile environment must be local-lab.")
    if profile.get("patient_count") != 100:
        raise ValueError("Profile must define exactly 100 patients.")
    if set(profile.get("cohort_conditions", {})) != {
        "PREVENTIVE", "PREDIABETES", "DIABETES", "HYPERTENSION",
        "CARDIOVASCULAR", "RESPIRATORY", "PEDIATRIC", "OLDER_ADULT",
        "IDENTITY_EDGE", "RESULT_LIFECYCLE",
    }:
        raise ValueError("Profile must define all ten population cohorts.")
    return profile


def build_records(profile: dict, *, probe: bool = False) -> list[dict]:
    numbers = [profile["probe_patient_number"]] if probe else range(1, profile["patient_count"] + 1)
    return [
        {
            "mrn": f"SYNTHMRN{number:06d}",
            "problem_external_id": f"{profile['problem_external_id_prefix']}{number:06d}01",
            "diagnosis_external_id": f"{profile['diagnosis_external_id_prefix']}{number:06d}01",
            "encounter_external_id": f"{profile['encounter_external_id_prefix']}{number:06d}01",
        }
        for number in numbers
    ]


def build_payload(profile: dict, *, probe: bool = False, verify_only: bool = False) -> dict:
    return {"profile": profile, "records": build_records(profile, probe=probe), "verify_only": verify_only}


def render_receiver(template: str, payload: dict, *, commit: bool) -> str:
    encoded = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    rendered = template
    for placeholder, value in {
        "__SYNTHETIC_PAYLOAD_BASE64__": encoded,
        "__SYNTHETIC_COMMIT__": "true" if commit else "false",
    }.items():
        if placeholder not in rendered:
            raise ValueError(f"Receiver placeholder missing: {placeholder}")
        rendered = rendered.replace(placeholder, value)
    return rendered


def invoke_receiver(source: str, *, container: str = DEFAULT_CONTAINER) -> dict:
    result = subprocess.run(
        ["docker", "exec", "-i", "--user", "apache", container, "php"],
        input=source, text=True, capture_output=True, check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Receiver did not return JSON.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ) from exc
    if result.returncode != 0 or payload.get("status") not in {"PASS", "VERIFIED"}:
        raise RuntimeError(
            "OpenEMR diagnosis receiver failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return payload


def execute(
    *, profile_path: Path = DEFAULT_PROFILE, receiver_path: Path = DEFAULT_RECEIVER,
    probe: bool = False, commit: bool = False, verify_only: bool = False,
    environment: str | None = None, confirm_patient_count: int | None = None,
    container: str = DEFAULT_CONTAINER,
) -> dict:
    profile = load_profile(profile_path)
    expected = len(build_records(profile, probe=probe))
    if commit:
        if environment != "local-lab":
            raise ValueError("Commit requires --environment local-lab.")
        if confirm_patient_count != expected:
            raise ValueError(f"Commit requires --confirm-patient-count {expected}.")
    template = receiver_path.read_text(encoding="utf-8")
    payload = build_payload(profile, probe=probe, verify_only=verify_only)
    return invoke_receiver(render_receiver(template, payload, commit=commit), container=container)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    result.add_argument("--receiver", type=Path, default=DEFAULT_RECEIVER)
    result.add_argument("--container", default=DEFAULT_CONTAINER)
    result.add_argument("--probe", action="store_true")
    result.add_argument("--commit", action="store_true")
    result.add_argument("--verify", action="store_true")
    result.add_argument("--environment")
    result.add_argument("--confirm-patient-count", type=int)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        result = execute(
            profile_path=args.profile, receiver_path=args.receiver, probe=args.probe,
            commit=args.commit, verify_only=args.verify, environment=args.environment,
            confirm_patient_count=args.confirm_patient_count, container=args.container,
        )
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"SYNTHETIC DIAGNOSES: FAIL - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
