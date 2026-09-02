from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = (
    PROJECT_ROOT / "fixtures" / "synthetic" / "master-data-profile.json"
)
DEFAULT_RECEIVER = Path(__file__).with_name("openemr_master_data_receiver.php")
DEFAULT_CONTAINER = "health-it-openemr-lab-openemr-1"
APPROVED_ENVIRONMENT = "local-lab"


class MasterDataError(RuntimeError):
    """Raised when the master-data contract cannot be satisfied."""


def load_profile(path: Path = DEFAULT_PROFILE) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    validate_profile(profile)
    return profile


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("environment") != APPROVED_ENVIRONMENT:
        raise MasterDataError("Profile environment must be local-lab.")
    if profile.get("synthetic_only") is not True:
        raise MasterDataError("Profile must declare synthetic_only=true.")
    if profile.get("provider_count") != 25:
        raise MasterDataError("Approved provider count is exactly 25.")
    if profile.get("facility_count") != 3:
        raise MasterDataError("Approved facility count is exactly 3.")

    facilities = profile.get("facilities", [])
    departments = profile.get("departments", [])
    distribution = profile.get("provider_distribution", [])

    if len(facilities) != 3:
        raise MasterDataError("Profile must contain three facilities.")
    if len(departments) != 8:
        raise MasterDataError("Profile must contain eight departments.")
    if sum(item["count"] for item in distribution) != 25:
        raise MasterDataError("Provider distribution must total 25.")

    facility_codes = {item["facility_code"] for item in facilities}
    if len(facility_codes) != len(facilities):
        raise MasterDataError("Facility codes must be unique.")

    department_codes = {item["code"] for item in departments}
    if len(department_codes) != len(departments):
        raise MasterDataError("Department codes must be unique.")

    for facility in facilities:
        if not facility["facility_code"].startswith("SYNFAC"):
            raise MasterDataError("Facility code is outside synthetic namespace.")
        if not facility["email"].endswith("@example.invalid"):
            raise MasterDataError("Facility email must use example.invalid.")
        if "facility_npi" in facility:
            raise MasterDataError("Synthetic facilities must not declare an NPI.")

    for department in departments:
        if department["facility_code"] not in facility_codes:
            raise MasterDataError("Department references an unknown facility.")

    for group in distribution:
        if group["department_code"] not in department_codes:
            raise MasterDataError("Provider group references an unknown department.")
        if not re.fullmatch(r"[A-Z0-9]{10}", group.get("taxonomy", "")):
            raise MasterDataError("Provider taxonomy must be a 10-character NUCC code.")


def build_master_data(profile: dict[str, Any]) -> dict[str, Any]:
    department_by_code = {
        department["code"]: department
        for department in profile["departments"]
    }

    providers: list[dict[str, Any]] = []
    sequence = 1

    for group in profile["provider_distribution"]:
        department = department_by_code[group["department_code"]]

        for _ in range(group["count"]):
            provider_id = f"SYNPROV{sequence:04d}"
            providers.append(
                {
                    "provider_id": provider_id,
                    "username": f"synprov{sequence:04d}",
                    "given_name": f"Provider{sequence:03d}",
                    "family_name": "Synthetic",
                    "email": f"synprov{sequence:04d}@example.invalid",
                    "phone": f"555-011-{sequence:04d}",
                    "specialty": group["specialty"],
                    "taxonomy": group["taxonomy"],
                    "department_code": group["department_code"],
                    "facility_code": department["facility_code"],
                    "active": True,
                    "authorized": True,
                }
            )
            sequence += 1

    if len(providers) != profile["provider_count"]:
        raise MasterDataError("Generated provider count does not match profile.")

    return {
        "profile_version": profile["profile_version"],
        "issue": profile["issue"],
        "environment": profile["environment"],
        "synthetic_only": profile["synthetic_only"],
        "source_system": profile["source_system"],
        "organization": profile["organization"],
        "facilities": profile["facilities"],
        "departments": profile["departments"],
        "providers": providers,
    }


def select_probe(data: dict[str, Any]) -> dict[str, Any]:
    probe = data.copy()
    facility = data["facilities"][0]
    provider = next(
        item
        for item in data["providers"]
        if item["facility_code"] == facility["facility_code"]
    )
    probe["facilities"] = [facility]
    probe["providers"] = [provider]
    probe["probe"] = True
    return probe


def validate_commit_confirmation(
    args: argparse.Namespace,
    data: dict[str, Any],
) -> None:
    expected_providers = len(data["providers"])
    expected_facilities = len(data["facilities"])

    if args.environment != APPROVED_ENVIRONMENT:
        raise MasterDataError("--environment must equal local-lab.")
    if args.confirm_provider_count != expected_providers:
        raise MasterDataError(
            "--confirm-provider-count must equal "
            f"{expected_providers} for this operation."
        )
    if args.confirm_facility_count != expected_facilities:
        raise MasterDataError(
            "--confirm-facility-count must equal "
            f"{expected_facilities} for this operation."
        )


def invoke_receiver(
    data: dict[str, Any],
    action: str,
    container: str,
    receiver_path: Path = DEFAULT_RECEIVER,
) -> dict[str, Any]:
    payload = dict(data)
    payload["action"] = action
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")

    command = [
        "docker",
        "exec",
        "-i",
        "--user",
        "apache",
        "-e",
        f"SYNTH_MASTER_DATA_B64={encoded}",
        container,
        "php",
    ]

    result = subprocess.run(
        command,
        input=receiver_path.read_bytes(),
        capture_output=True,
        check=False,
    )

    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()

    if result.returncode != 0:
        raise MasterDataError(
            "OpenEMR master-data receiver failed.\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise MasterDataError(
            f"Receiver did not return JSON.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        ) from exc

    if response.get("status") not in {"PASS", "VERIFIED"}:
        raise MasterDataError(json.dumps(response, indent=2))

    return response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision deterministic synthetic OpenEMR master data."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--environment")
    parser.add_argument("--confirm-provider-count", type=int)
    parser.add_argument("--confirm-facility-count", type=int)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        profile = load_profile(args.profile)
        data = build_master_data(profile)

        if args.probe:
            data = select_probe(data)

        if args.verify:
            response = invoke_receiver(data, "verify", args.container)
            print(json.dumps(response, indent=2))
            return 0

        if not args.commit:
            print("SYNTHETIC MASTER DATA: DRY RUN")
            print(json.dumps(data, indent=2))
            return 0

        validate_commit_confirmation(args, data)
        response = invoke_receiver(data, "commit", args.container)
        print(json.dumps(response, indent=2))
        return 0

    except (MasterDataError, OSError, KeyError, ValueError) as exc:
        print(f"SYNTHETIC MASTER DATA: FAIL - {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
