"""Guarded deterministic encounter and vitals provisioning for local OpenEMR."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = (
    ROOT / "fixtures" / "synthetic" / "encounter-vitals-profile.json"
)
DEFAULT_RECEIVER = Path(__file__).with_name(
    "openemr_encounter_vitals_receiver.php"
)
DEFAULT_CONTAINER = "health-it-openemr-lab-openemr-1"


def load_profile(path: Path = DEFAULT_PROFILE) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))

    if profile.get("synthetic_only") is not True:
        raise ValueError("Profile must declare synthetic_only=true.")

    if profile.get("environment") != "local-lab":
        raise ValueError("Profile environment must be local-lab.")

    if profile.get("patient_count") != 100:
        raise ValueError("Profile must define exactly 100 patients.")

    if profile.get("encounters_per_patient") != 3:
        raise ValueError(
            "Profile must define exactly three encounters per patient."
        )

    visit_schedule = profile.get("visit_schedule")

    if not isinstance(visit_schedule, list):
        raise ValueError("Profile must define visit_schedule as a list.")

    if len(visit_schedule) != profile["encounters_per_patient"]:
        raise ValueError(
            "Visit schedule must match encounters_per_patient."
        )

    sequences = [visit.get("sequence") for visit in visit_schedule]

    if sequences != [1, 2, 3]:
        raise ValueError(
            "Visit schedule sequences must be exactly 1, 2, and 3."
        )

    offsets = [visit.get("offset_days") for visit in visit_schedule]

    if (
        any(not isinstance(offset, int) for offset in offsets)
        or offsets != sorted(offsets)
        or len(set(offsets)) != len(offsets)
    ):
        raise ValueError(
            "Visit offsets must be unique ascending integers."
        )

    return profile


def build_records(
    profile: dict,
    *,
    probe: bool = False,
) -> list[dict]:
    patient_count = 1 if probe else profile["patient_count"]
    base = datetime.strptime(profile["base_date"], "%Y-%m-%d")
    records = []

    for patient_number in range(1, patient_count + 1):
        patient_base = base + timedelta(
            days=patient_number - 1,
            hours=9 + patient_number % 7,
        )

        for visit in profile["visit_schedule"]:
            visit_sequence = int(visit["sequence"])
            encounter_at = patient_base + timedelta(
                days=int(visit["offset_days"])
            )
            vitals_at = encounter_at + timedelta(
                minutes=profile["vitals"]["minutes_after_encounter"]
            )

            records.append(
                {
                    "mrn": f"SYNTHMRN{patient_number:06d}",
                    "visit_sequence": visit_sequence,
                    "encounter_external_id": (
                        f"SYNENC{patient_number:06d}"
                        f"{visit_sequence:02d}"
                    ),
                    "vitals_external_id": (
                        f"SYNVIT{patient_number:06d}"
                        f"{visit_sequence:02d}"
                    ),
                    "encounter_at": encounter_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "vitals_at": vitals_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )

    return records


def build_payload(
    profile: dict,
    *,
    probe: bool = False,
    verify_only: bool = False,
) -> dict:
    records = build_records(profile, probe=probe)

    return {
        "profile": profile,
        "expected_patients": 1 if probe else profile["patient_count"],
        "expected_records": len(records),
        "records": records,
        "verify_only": verify_only,
    }


def render_receiver(
    template: str,
    payload: dict,
    *,
    commit: bool,
) -> str:
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()

    replacements = {
        "__SYNTHETIC_PAYLOAD_BASE64__": encoded,
        "__SYNTHETIC_COMMIT__": "true" if commit else "false",
    }

    rendered = template

    for placeholder, value in replacements.items():
        if placeholder not in rendered:
            raise ValueError(
                f"Receiver placeholder missing: {placeholder}"
            )

        rendered = rendered.replace(placeholder, value)

    return rendered


def invoke_receiver(
    source: str,
    *,
    container: str = DEFAULT_CONTAINER,
) -> dict:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "--user",
            "apache",
            container,
            "php",
        ],
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
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        ) from exc

    if (
        result.returncode != 0
        or payload.get("status") not in {"PASS", "VERIFIED"}
    ):
        raise RuntimeError(
            "OpenEMR encounter/vitals receiver failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return payload


def execute(
    *,
    profile_path: Path = DEFAULT_PROFILE,
    receiver_path: Path = DEFAULT_RECEIVER,
    probe: bool = False,
    commit: bool = False,
    verify_only: bool = False,
    environment: str | None = None,
    confirm_patient_count: int | None = None,
    container: str = DEFAULT_CONTAINER,
) -> dict:
    profile = load_profile(profile_path)
    expected_patients = 1 if probe else profile["patient_count"]

    if commit:
        if environment != "local-lab":
            raise ValueError(
                "Commit requires --environment local-lab."
            )

        if confirm_patient_count != expected_patients:
            raise ValueError(
                "Commit requires --confirm-patient-count "
                f"{expected_patients}."
            )

    template = receiver_path.read_text(encoding="utf-8")
    payload = build_payload(
        profile,
        probe=probe,
        verify_only=verify_only,
    )
    source = render_receiver(
        template,
        payload,
        commit=commit,
    )

    return invoke_receiver(
        source,
        container=container,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
    )
    result.add_argument(
        "--receiver",
        type=Path,
        default=DEFAULT_RECEIVER,
    )
    result.add_argument(
        "--container",
        default=DEFAULT_CONTAINER,
    )
    result.add_argument("--probe", action="store_true")
    result.add_argument("--commit", action="store_true")
    result.add_argument("--verify", action="store_true")
    result.add_argument("--environment")
    result.add_argument(
        "--confirm-patient-count",
        type=int,
    )

    return result


def main() -> int:
    args = parser().parse_args()

    try:
        result = execute(
            profile_path=args.profile,
            receiver_path=args.receiver,
            probe=args.probe,
            commit=args.commit,
            verify_only=args.verify,
            environment=args.environment,
            confirm_patient_count=args.confirm_patient_count,
            container=args.container,
        )
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"SYNTHETIC ENCOUNTER/VITALS: FAIL - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())