"""Guarded deterministic laboratory-order provisioning for local OpenEMR."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = (
    ROOT / "fixtures" / "synthetic" / "laboratory-orders-profile.json"
)
DEFAULT_RECEIVER = Path(__file__).with_name(
    "openemr_laboratory_order_receiver.php"
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
    if profile.get("requisitions_per_patient") != 1:
        raise ValueError("This phase must define one requisition per patient.")
    if profile.get("encounter_sequence") != 1:
        raise ValueError("This phase must use the first historical encounter.")

    targets = profile.get("phase_targets", {})
    if targets.get("requisitions") != 100:
        raise ValueError("Phase target must define exactly 100 requisitions.")
    if targets.get("ordered_test_lines") != 100:
        raise ValueError("Phase target must define exactly 100 ordered-test lines.")

    laboratory = profile.get("laboratory", {})
    if laboratory.get("recv_app_id") != "SYNLIS":
        raise ValueError("Synthetic laboratory receiving application must be SYNLIS.")
    if "DORN" in json.dumps(laboratory).upper():
        raise ValueError("Synthetic laboratory configuration must be vendor-neutral.")

    orderable = profile.get("orderable", {})
    if orderable.get("procedure_code") != "2345-7":
        raise ValueError("Initial orderable must use LOINC 2345-7.")
    if orderable.get("procedure_type") != "ord":
        raise ValueError("Initial procedure type must be ord.")

    return profile


def build_records(
    profile: dict,
    *,
    probe: bool = False,
) -> list[dict]:
    patient_numbers = (
        [profile["probe_patient_number"]]
        if probe
        else range(1, profile["patient_count"] + 1)
    )
    encounter_sequence = int(profile["encounter_sequence"])
    prefix = profile["order_external_id_prefix"]

    return [
        {
            "mrn": f"SYNTHMRN{patient_number:06d}",
            "encounter_external_id": (
                f"SYNENC{patient_number:06d}{encounter_sequence:02d}"
            ),
            "order_external_id": (
                f"{prefix}{patient_number:06d}{encounter_sequence:02d}"
            ),
            "encounter_sequence": encounter_sequence,
        }
        for patient_number in patient_numbers
    ]


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
        "expected_requisitions": len(records),
        "expected_order_lines": len(records),
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
    rendered = template

    for placeholder, value in {
        "__SYNTHETIC_PAYLOAD_BASE64__": encoded,
        "__SYNTHETIC_COMMIT__": "true" if commit else "false",
    }.items():
        if placeholder not in rendered:
            raise ValueError(f"Receiver placeholder missing: {placeholder}")
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
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ) from exc

    if (
        result.returncode != 0
        or payload.get("status") not in {"PASS", "VERIFIED"}
    ):
        raise RuntimeError(
            "OpenEMR laboratory-order receiver failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
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
            raise ValueError("Commit requires --environment local-lab.")
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
    return invoke_receiver(
        render_receiver(template, payload, commit=commit),
        container=container,
    )


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
        print(f"SYNTHETIC LABORATORY ORDERS: FAIL - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
