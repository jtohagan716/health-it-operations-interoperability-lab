"""Guarded deterministic encounter and vitals provisioning for local OpenEMR."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ROOT / "fixtures" / "synthetic" / "encounter-vitals-profile.json"
DEFAULT_RECEIVER = Path(__file__).with_name("openemr_encounter_vitals_receiver.php")
DEFAULT_CONTAINER = "health-it-openemr-lab-openemr-1"


def load_profile(path: Path = DEFAULT_PROFILE) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("synthetic_only") is not True:
        raise ValueError("Profile must declare synthetic_only=true.")
    if profile.get("environment") != "local-lab":
        raise ValueError("Profile environment must be local-lab.")
    if profile.get("patient_count") != 100:
        raise ValueError("Profile must define exactly 100 patients.")
    return profile


def build_records(profile: dict, *, probe: bool = False) -> list[dict]:
    count = 1 if probe else profile["patient_count"]
    base = datetime.strptime(profile["base_date"], "%Y-%m-%d")
    records = []
    for number in range(1, count + 1):
        encounter_at = base + timedelta(days=number - 1, hours=9 + number % 7)
        vitals_at = encounter_at + timedelta(minutes=profile["vitals"]["minutes_after_encounter"])
        records.append({
            "mrn": f"SYNTHMRN{number:06d}",
            "encounter_external_id": f"SYNENC{number:06d}01",
            "vitals_external_id": f"SYNVIT{number:06d}01",
            "encounter_at": encounter_at.strftime("%Y-%m-%d %H:%M:%S"),
            "vitals_at": vitals_at.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return records


def build_payload(profile: dict, *, probe: bool = False, verify_only: bool = False) -> dict:
    return {"profile": profile, "records": build_records(profile, probe=probe), "verify_only": verify_only}


def render_receiver(template: str, payload: dict, *, commit: bool) -> str:
    encoded = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    replacements = {
        "__SYNTHETIC_PAYLOAD_BASE64__": encoded,
        "__SYNTHETIC_COMMIT__": "true" if commit else "false",
    }
    rendered = template
    for placeholder, value in replacements.items():
        if placeholder not in rendered:
            raise ValueError(f"Receiver placeholder missing: {placeholder}")
        rendered = rendered.replace(placeholder, value)
    return rendered


def invoke_receiver(source: str, *, container: str = DEFAULT_CONTAINER) -> dict:
    result = subprocess.run(
        ["docker", "exec", "-i", "--user", "apache", container, "php"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
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
            "OpenEMR encounter/vitals receiver failed.\n"
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
    records = build_records(profile, probe=probe)
    expected = len(records)
    if commit:
        if environment != "local-lab":
            raise ValueError("Commit requires --environment local-lab.")
        if confirm_patient_count != expected:
            raise ValueError(f"Commit requires --confirm-patient-count {expected}.")
    template = receiver_path.read_text(encoding="utf-8")
    payload = build_payload(profile, probe=probe, verify_only=verify_only)
    source = render_receiver(template, payload, commit=commit)
    return invoke_receiver(source, container=container)


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
        print(f"SYNTHETIC ENCOUNTER/VITALS: FAIL - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
