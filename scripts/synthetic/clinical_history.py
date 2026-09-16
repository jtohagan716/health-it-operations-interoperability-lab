"""Deterministic synthetic medication, allergy, and immunization history."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROFILE = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "clinical-history-profile.json"
)

POPULATION_PROFILE = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "population-profile.json"
)

DEFAULT_RECEIVER = (
    ROOT
    / "scripts"
    / "synthetic"
    / "openemr_clinical_history_receiver.php"
)

DEFAULT_OPENEMR_CONTAINER = (
    "health-it-openemr-lab-openemr-1"
)

PAYLOAD_PLACEHOLDER = "__PAYLOAD_BASE64__"


class ClinicalHistoryError(ValueError):
    """Raised when the synthetic clinical-history contract is invalid."""


def load_profile(path: Path = DEFAULT_PROFILE) -> dict:
    profile = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    if profile.get("synthetic_only") is not True:
        raise ClinicalHistoryError(
            "Profile must declare synthetic_only=true."
        )

    if profile.get("environment") != "local-lab":
        raise ClinicalHistoryError(
            "Profile environment must be local-lab."
        )

    if (
        profile.get("source_system")
        != "SYNTHETIC_POPULATION_V1"
    ):
        raise ClinicalHistoryError(
            "Unexpected source system."
        )

    if profile.get("patient_count") != 100:
        raise ClinicalHistoryError(
            "Profile must define exactly 100 patients."
        )

    expected_targets = {
        "medications": 200,
        "allergies": 100,
        "immunizations": 200,
    }

    if profile.get("targets") != expected_targets:
        raise ClinicalHistoryError(
            "Clinical-history targets must equal "
            f"{expected_targets}."
        )

    try:
        datetime.strptime(
            profile["base_date"],
            "%Y-%m-%d",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ClinicalHistoryError(
            "Profile must define base_date as YYYY-MM-DD."
        ) from exc

    required_prefixes = {
        "medication",
        "allergy",
        "immunization",
    }

    if (
        set(profile.get("external_id_prefixes", {}))
        != required_prefixes
    ):
        raise ClinicalHistoryError(
            "Profile must define medication, allergy, and "
            "immunization external-ID prefixes."
        )

    for key in (
        "medication_catalog",
        "allergy_catalog",
        "immunization_catalog",
        "cohort_medications",
        "temporal_model",
    ):
        if not profile.get(key):
            raise ClinicalHistoryError(
                f"Profile section {key} must not be empty."
            )

    return profile


def load_population_profile(
    path: Path = POPULATION_PROFILE,
) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8-sig")
    )


def cohort_for(
    sequence: int,
    population_profile: dict,
) -> str:
    cohorts = population_profile["cohorts"]

    if sequence < 1 or sequence > 100:
        raise ClinicalHistoryError(
            "Patient sequence must be between 1 and 100."
        )

    return cohorts[
        (sequence - 1) % len(cohorts)
    ]


def patient_mrn(sequence: int) -> str:
    if sequence < 1 or sequence > 100:
        raise ClinicalHistoryError(
            "Patient sequence must be between 1 and 100."
        )

    return f"SYNTHMRN{sequence:06d}"


def external_id(
    prefix: str,
    patient_sequence: int,
    record_sequence: int,
) -> str:
    if not prefix:
        raise ClinicalHistoryError(
            "External-ID prefix must not be empty."
        )

    if (
        patient_sequence < 1
        or patient_sequence > 100
    ):
        raise ClinicalHistoryError(
            "Patient sequence must be between 1 and 100."
        )

    if record_sequence < 1:
        raise ClinicalHistoryError(
            "Record sequence must be positive."
        )

    return (
        f"{prefix}"
        f"{patient_sequence:06d}"
        f"{record_sequence:02d}"
    )


def patient_base_date(
    profile: dict,
    sequence: int,
) -> datetime:
    base = datetime.strptime(
        profile["base_date"],
        "%Y-%m-%d",
    )

    return base + timedelta(
        days=sequence - 1
    )


def build_medications(
    profile: dict,
    population_profile: dict,
) -> list[dict]:
    catalog = profile["medication_catalog"]
    assignments = profile["cohort_medications"]
    temporal = profile["temporal_model"]

    prefix = profile[
        "external_id_prefixes"
    ]["medication"]

    records: list[dict] = []

    expected_cohorts = set(
        population_profile["cohorts"]
    )

    if set(assignments) != expected_cohorts:
        raise ClinicalHistoryError(
            "Medication assignments must define "
            "every population cohort."
        )

    for sequence in range(1, 101):
        cohort = cohort_for(
            sequence,
            population_profile,
        )

        medication_keys = assignments[
            cohort
        ]

        if not medication_keys:
            raise ClinicalHistoryError(
                f"Cohort {cohort} has no "
                "medication assignments."
            )

        patient_base = patient_base_date(
            profile,
            sequence,
        )

        for (
            record_sequence,
            medication_key,
        ) in enumerate(
            medication_keys,
            start=1,
        ):
            if medication_key not in catalog:
                raise ClinicalHistoryError(
                    "Unknown medication catalog key: "
                    f"{medication_key}"
                )

            start_date = (
                patient_base
                - timedelta(
                    days=temporal[
                        "medication_days_before_base"
                    ]
                )
                + timedelta(
                    days=(
                        (record_sequence - 1)
                        * temporal[
                            "medication_record_spacing_days"
                        ]
                    )
                )
            )

            records.append(
                {
                    "mrn": patient_mrn(
                        sequence
                    ),
                    "cohort": cohort,
                    "external_id": external_id(
                        prefix,
                        sequence,
                        record_sequence,
                    ),
                    "start_date": (
                        start_date.strftime(
                            "%Y-%m-%d"
                        )
                    ),
                    **catalog[
                        medication_key
                    ],
                }
            )

    expected = profile[
        "targets"
    ]["medications"]

    if len(records) != expected:
        raise ClinicalHistoryError(
            "Medication generation did not "
            "produce the required target of "
            f"{expected}; generated "
            f"{len(records)}."
        )

    return records


def build_allergies(
    profile: dict,
    population_profile: dict,
) -> list[dict]:
    catalog = profile[
        "allergy_catalog"
    ]

    temporal = profile[
        "temporal_model"
    ]

    prefix = profile[
        "external_id_prefixes"
    ]["allergy"]

    records: list[dict] = []

    for sequence in range(1, 101):
        template = catalog[
            (sequence - 1)
            % len(catalog)
        ]

        patient_base = patient_base_date(
            profile,
            sequence,
        )

        begdate = (
            patient_base
            - timedelta(
                days=temporal[
                    "allergy_days_before_base"
                ]
            )
        )

        records.append(
            {
                "mrn": patient_mrn(
                    sequence
                ),
                "cohort": cohort_for(
                    sequence,
                    population_profile,
                ),
                "external_id": external_id(
                    prefix,
                    sequence,
                    1,
                ),
                "begdate": begdate.strftime(
                    "%Y-%m-%d"
                ),
                **template,
            }
        )

    expected = profile[
        "targets"
    ]["allergies"]

    if len(records) != expected:
        raise ClinicalHistoryError(
            "Allergy generation did not "
            "produce the required target."
        )

    return records


def build_immunizations(
    profile: dict,
    population_profile: dict,
) -> list[dict]:
    catalog = profile[
        "immunization_catalog"
    ]

    temporal = profile[
        "temporal_model"
    ]

    prefix = profile[
        "external_id_prefixes"
    ]["immunization"]

    records: list[dict] = []

    if len(catalog) < 2:
        raise ClinicalHistoryError(
            "At least two immunization "
            "templates are required."
        )

    for sequence in range(1, 101):
        first_index = (
            (sequence - 1)
            % len(catalog)
        )

        second_index = (
            (first_index + 1)
            % len(catalog)
        )

        patient_base = patient_base_date(
            profile,
            sequence,
        )

        for (
            record_sequence,
            index,
        ) in enumerate(
            (
                first_index,
                second_index,
            ),
            start=1,
        ):
            administered_date = (
                patient_base
                - timedelta(
                    days=temporal[
                        "immunization_days_before_base"
                    ]
                )
                + timedelta(
                    days=(
                        (record_sequence - 1)
                        * temporal[
                            "immunization_record_spacing_days"
                        ]
                    )
                )
            )

            records.append(
                {
                    "mrn": patient_mrn(
                        sequence
                    ),
                    "cohort": cohort_for(
                        sequence,
                        population_profile,
                    ),
                    "external_id": external_id(
                        prefix,
                        sequence,
                        record_sequence,
                    ),
                    "administered_date": (
                        administered_date.strftime(
                            "%Y-%m-%d"
                        )
                    ),
                    **catalog[index],
                }
            )

    expected = profile[
        "targets"
    ]["immunizations"]

    if len(records) != expected:
        raise ClinicalHistoryError(
            "Immunization generation did not "
            "produce the required target."
        )

    return records


def build_clinical_history(
    profile: dict,
    population_profile: dict,
) -> dict[str, list[dict]]:
    return {
        "medications": build_medications(
            profile,
            population_profile,
        ),
        "allergies": build_allergies(
            profile,
            population_profile,
        ),
        "immunizations": build_immunizations(
            profile,
            population_profile,
        ),
    }


def build_manifest(
    profile: dict,
    population_profile: dict,
) -> dict:
    """Build the expected-state clinical-history manifest."""

    history = build_clinical_history(
        profile,
        population_profile,
    )

    records: list[dict] = []

    for domain, entity_type in (
        (
            "medications",
            "medication",
        ),
        (
            "allergies",
            "allergy",
        ),
        (
            "immunizations",
            "immunization",
        ),
    ):
        for record in history[domain]:
            records.append(
                {
                    "entity_type": (
                        entity_type
                    ),
                    "logical_key": (
                        record[
                            "external_id"
                        ]
                    ),
                    "source_system": (
                        profile[
                            "source_system"
                        ]
                    ),
                    **record,
                }
            )

    expected_counts = {
        domain: len(
            domain_records
        )
        for (
            domain,
            domain_records,
        ) in history.items()
    }

    outcomes = {
        domain: {
            "expected": expected,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "reconciled": 0,
        }
        for (
            domain,
            expected,
        ) in expected_counts.items()
    }

    return {
        "run_id": (
            f"SYNTH-"
            f"{profile['seed']}"
            "-031"
        ),
        "profile_version": (
            profile[
                "profile_version"
            ]
        ),
        "seed": profile["seed"],
        "environment": (
            profile[
                "environment"
            ]
        ),
        "synthetic_only": (
            profile[
                "synthetic_only"
            ]
        ),
        "generated_at": (
            datetime.now(
                UTC
            ).isoformat()
        ),
        "source_system": (
            profile[
                "source_system"
            ]
        ),
        "expected_counts": (
            expected_counts
        ),
        "outcomes": outcomes,
        "records": records,
    }


def select_patient_probe(
    manifest: dict,
    mrn: str,
) -> dict:
    """Return records for exactly one synthetic patient."""

    if not mrn.startswith(
        "SYNTHMRN"
    ):
        raise ClinicalHistoryError(
            "Probe patient must use the "
            "SYNTHMRN identifier namespace."
        )

    records = [
        record
        for record in manifest[
            "records"
        ]
        if record["mrn"] == mrn
    ]

    if not records:
        raise ClinicalHistoryError(
            "No clinical-history records "
            f"found for patient {mrn}."
        )

    expected_counts = {
        "medications": sum(
            record[
                "entity_type"
            ] == "medication"
            for record in records
        ),
        "allergies": sum(
            record[
                "entity_type"
            ] == "allergy"
            for record in records
        ),
        "immunizations": sum(
            record[
                "entity_type"
            ] == "immunization"
            for record in records
        ),
    }

    outcomes = {
        domain: {
            "expected": expected,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "reconciled": 0,
        }
        for (
            domain,
            expected,
        ) in expected_counts.items()
    }

    probe = dict(manifest)

    probe[
        "expected_counts"
    ] = expected_counts

    probe["outcomes"] = outcomes
    probe["records"] = records

    return probe

def validate_commit_confirmation(
    args: argparse.Namespace,
    manifest: dict,
) -> None:
    """Enforce explicit safeguards before any clinical-history write."""

    if not args.probe:
        raise ClinicalHistoryError(
            "--commit requires --probe so writes are limited "
            "to exactly one synthetic patient."
        )

    if args.environment != "local-lab":
        raise ClinicalHistoryError(
            "--environment must equal local-lab for commit."
        )

    expected = len(
        manifest["records"]
    )

    if args.confirm_record_count is None:
        raise ClinicalHistoryError(
            "--confirm-record-count is required for commit."
        )

    if args.confirm_record_count != expected:
        raise ClinicalHistoryError(
            "--confirm-record-count must equal "
            f"{expected} for this operation."
        )

    if expected < 1:
        raise ClinicalHistoryError(
            "Commit manifest contains no records."
        )

    mrns = {
        record["mrn"]
        for record in manifest["records"]
    }

    if len(mrns) != 1:
        raise ClinicalHistoryError(
            "Commit manifest must contain records "
            "for exactly one patient."
        )

    mrn = next(iter(mrns))

    if not mrn.startswith(
        "SYNTHMRN"
    ):
        raise ClinicalHistoryError(
            "Commit patient is outside the "
            "synthetic MRN namespace."
        )

    if mrn != args.probe:
        raise ClinicalHistoryError(
            "Commit manifest patient does not "
            "match --probe."
        )

    for record in manifest["records"]:
        if (
            record.get("source_system")
            != "SYNTHETIC_POPULATION_V1"
        ):
            raise ClinicalHistoryError(
                "Commit record has an unapproved "
                "source system."
            )

        logical_key = record.get(
            "logical_key",
            "",
        )

        if not logical_key.startswith(
            (
                "SYNMED",
                "SYNALG",
                "SYNIMM",
            )
        ):
            raise ClinicalHistoryError(
                "Commit record is outside the "
                "synthetic logical-key namespace."
            )


def invoke_receiver(
    manifest: dict,
    action: str,
    container: str = DEFAULT_OPENEMR_CONTAINER,
    receiver_path: Path = DEFAULT_RECEIVER,
) -> dict:
    """Invoke the guarded clinical-history receiver inside OpenEMR."""

    if action not in {
        "verify",
        "commit",
    }:
        raise ClinicalHistoryError(
            "Unsupported clinical-history receiver action: "
            f"{action}"
        )

    payload = dict(manifest)
    payload["action"] = action

    encoded = base64.b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")

    template = receiver_path.read_text(
        encoding="utf-8"
    )

    if PAYLOAD_PLACEHOLDER not in template:
        raise ClinicalHistoryError(
            "Clinical-history receiver payload placeholder is missing."
        )

    rendered = template.replace(
        PAYLOAD_PLACEHOLDER,
        encoded,
    )

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
        input=rendered.encode("utf-8"),
        capture_output=True,
        check=False,
    )

    stdout = result.stdout.decode(
        "utf-8",
        errors="replace",
    ).strip()

    stderr = result.stderr.decode(
        "utf-8",
        errors="replace",
    ).strip()

    if result.returncode != 0:
        raise ClinicalHistoryError(
            "OpenEMR clinical-history receiver failed.\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

    try:
        response = json.loads(
            stdout
        )
    except json.JSONDecodeError as exc:
        raise ClinicalHistoryError(
            "Clinical-history receiver did not return JSON.\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        ) from exc

    allowed_statuses = {
        "verify": {
            "VERIFIED",
        },
        "commit": {
            "PASS",
            "COMMITTED",
        },
    }

    if (
        response.get("status")
        not in allowed_statuses[action]
    ):
        raise ClinicalHistoryError(
            json.dumps(
                response,
                indent=2,
            )
        )

    return response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic synthetic "
            "medication, allergy, and "
            "immunization history."
        )
    )

    action = parser.add_mutually_exclusive_group()

    action.add_argument(
        "--verify",
        action="store_true",
        help=(
            "Verify the generated clinical-history manifest "
            "against the local OpenEMR environment without "
            "writing data."
        ),
    )

    action.add_argument(
        "--commit",
        action="store_true",
        help=(
            "Commit the selected synthetic patient's "
            "clinical history to the approved local "
            "OpenEMR lab."
        ),
    )

    parser.add_argument(
        "--probe",
        metavar="SYNTHMRN",
        help=(
            "Return or operate on the clinical-history "
            "manifest for one synthetic patient."
        ),
    )

    parser.add_argument(
        "--environment",
        help=(
            "Required for commit and must equal local-lab."
        ),
    )

    parser.add_argument(
        "--confirm-record-count",
        type=int,
        help=(
            "Required for commit and must equal the exact "
            "number of records selected by --probe."
        ),
    )

    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
    )

    parser.add_argument(
        "--container",
        default=DEFAULT_OPENEMR_CONTAINER,
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    args = build_parser().parse_args(
        argv
    )

    try:
        profile = load_profile(
            args.profile
        )

        population_profile = (
            load_population_profile()
        )

        manifest = build_manifest(
            profile,
            population_profile,
        )

        if args.probe:
            manifest = (
                select_patient_probe(
                    manifest,
                    args.probe,
                )
            )

        if args.verify:
            response = invoke_receiver(
                manifest,
                "verify",
                args.container,
            )

            print(
                json.dumps(
                    response,
                    indent=2,
                )
            )

            return 0

        if args.commit:
            validate_commit_confirmation(
                args,
                manifest,
            )

            response = invoke_receiver(
                manifest,
                "commit",
                args.container,
            )

            print(
                json.dumps(
                    response,
                    indent=2,
                )
            )

            return 0

        print(
            "SYNTHETIC CLINICAL HISTORY: "
            "DRY RUN"
        )

        print(
            json.dumps(
                manifest,
                indent=2,
            )
        )

        return 0

    except (
        ClinicalHistoryError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            "SYNTHETIC CLINICAL HISTORY: "
            f"FAIL - {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )