import argparse
import base64
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.hl7.oru_scenario import (
    build_oru_segments,
    load_scenario,
)
from scripts.hl7.scenario_runtime import (
    generate_control_id,
)


DEFAULT_OPENEMR_CONTAINER = (
    "health-it-openemr-lab-openemr-1"
)
DEFAULT_RECEIVER_TEMPLATE = (
    Path(__file__).with_name(
        "openemr_oru_receiver.php"
    )
)


@dataclass(frozen=True)
class OpenEmrTarget:
    order_id: int
    patient_id: int
    encounter_id: int
    lab_id: int


@dataclass(frozen=True)
class OpenEmrIngestion:
    dry_run: dict
    committed: dict | None


def _fields(
    segment: str,
    *,
    minimum_length: int,
) -> list[str]:
    values = segment.split("|")

    if len(values) < minimum_length:
        values.extend(
            [""] * (minimum_length - len(values))
        )

    return values


def _find_segment(
    segments: list[str],
    name: str,
) -> int:
    prefix = f"{name}|"

    for index, segment in enumerate(segments):
        if segment.startswith(prefix):
            return index

    raise ValueError(
        f"Required {name} segment was not found."
    )


def build_openemr_oru_segments(
    scenario: dict,
    target: OpenEmrTarget,
    *,
    message_control_id: str,
    filler_id: str,
    commit: bool,
) -> list[str]:
    if not filler_id.strip():
        raise ValueError(
            "OpenEMR filler ID must not be blank."
        )

    segments = build_oru_segments(
        scenario,
        message_control_id=message_control_id,
    )

    msh_index = _find_segment(segments, "MSH")
    msh = _fields(
        segments[msh_index],
        minimum_length=12,
    )
    msh[2] = "DORN"
    msh[3] = "LAB"
    msh[4] = "OEMR"
    msh[5] = "INTEROPLAB"
    segments[msh_index] = "|".join(msh)

    pid_index = _find_segment(segments, "PID")
    pid = _fields(
        segments[pid_index],
        minimum_length=14,
    )
    segments[pid_index] = "|".join(pid)

    pv1 = [""] * 20
    pv1[0] = "PV1"
    pv1[1] = "1"
    pv1[2] = "O"
    pv1[19] = str(target.encounter_id)

    orc = ["ORC", "RE", str(target.order_id)]

    obr_index = _find_segment(segments, "OBR")
    obr = _fields(
        segments[obr_index],
        minimum_length=26,
    )
    obr[2] = str(target.order_id)
    obr[3] = filler_id if commit else ""
    obr[22] = scenario["order"][
        "observation_timestamp"
    ]
    segments[obr_index] = "|".join(obr)

    obx_index = _find_segment(segments, "OBX")
    obx = _fields(
        segments[obx_index],
        minimum_length=15,
    )
    obx[14] = scenario["order"][
        "observation_timestamp"
    ]
    segments[obx_index] = "|".join(obx)

    return (
        segments[: pid_index + 1]
        + ["|".join(pv1), "|".join(orc)]
        + segments[pid_index + 1 :]
    )


def encode_text(value: str) -> str:
    return base64.b64encode(
        value.encode("utf-8")
    ).decode("ascii")


def render_receiver(
    template: str,
    *,
    segments: list[str],
    target: OpenEmrTarget,
    procedure_code: str,
    filler_id: str,
    commit: bool,
    allow_existing_results: bool,
) -> str:
    hl7 = "\r".join(segments) + "\r"
    replacements = {
        "__OPENEMR_ORDER_ID__": str(
            target.order_id
        ),
        "__OPENEMR_PATIENT_ID__": str(
            target.patient_id
        ),
        "__OPENEMR_ENCOUNTER_ID__": str(
            target.encounter_id
        ),
        "__OPENEMR_LAB_ID__": str(target.lab_id),
        "__OPENEMR_COMMIT__": (
            "true" if commit else "false"
        ),
        "__OPENEMR_ALLOW_EXISTING__": (
            "true"
            if allow_existing_results
            else "false"
        ),
        "__OPENEMR_PROCEDURE_CODE_BASE64__": (
            encode_text(procedure_code)
        ),
        "__OPENEMR_FILLER_ID_BASE64__": (
            encode_text(filler_id)
        ),
        "__OPENEMR_HL7_BASE64__": encode_text(hl7),
    }

    rendered = template

    for placeholder, value in replacements.items():
        if placeholder not in rendered:
            raise ValueError(
                "Receiver template placeholder is missing: "
                f"{placeholder}"
            )

        rendered = rendered.replace(
            placeholder,
            value,
        )

    remaining = [
        placeholder
        for placeholder in replacements
        if placeholder in rendered
    ]

    if remaining:
        raise ValueError(
            "Receiver template contains unresolved "
            f"placeholders: {remaining}"
        )

    return rendered


def invoke_receiver(
    php_source: str,
    *,
    container: str = DEFAULT_OPENEMR_CONTAINER,
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
        input=php_source,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "OpenEMR ORU receiver failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "OpenEMR ORU receiver returned invalid JSON.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        ) from exc

    return payload


def execute_openemr_scenario(
    scenario_path: Path | str,
    target: OpenEmrTarget,
    *,
    commit: bool = False,
    confirm_order_id: int | None = None,
    allow_existing_results: bool = False,
    container: str = DEFAULT_OPENEMR_CONTAINER,
    receiver_template: Path = DEFAULT_RECEIVER_TEMPLATE,
) -> OpenEmrIngestion:
    if commit and confirm_order_id != target.order_id:
        raise ValueError(
            "Commit requires --confirm-order-id matching "
            f"Order ID {target.order_id}."
        )

    scenario = load_scenario(scenario_path)
    procedure_code = scenario["order"][
        "service_code"
    ]
    filler_id = scenario["order"]["filler_number"]
    template = receiver_template.read_text(
        encoding="utf-8"
    )
    control_id = generate_control_id(
        f"OPENEMR-ORU-{target.order_id}",
        suffix_length=10,
    )

    dry_segments = build_openemr_oru_segments(
        scenario,
        target,
        message_control_id=control_id,
        filler_id=filler_id,
        commit=False,
    )
    dry_source = render_receiver(
        template,
        segments=dry_segments,
        target=target,
        procedure_code=procedure_code,
        filler_id=filler_id,
        commit=False,
        allow_existing_results=False,
    )
    dry_run = invoke_receiver(
        dry_source,
        container=container,
    )

    if dry_run.get("status") != "DRY_RUN_PASSED":
        raise RuntimeError(
            "OpenEMR ORU dry run did not pass: "
            f"{dry_run}"
        )

    committed = None

    if commit:
        commit_segments = build_openemr_oru_segments(
            scenario,
            target,
            message_control_id=control_id,
            filler_id=filler_id,
            commit=True,
        )
        commit_source = render_receiver(
            template,
            segments=commit_segments,
            target=target,
            procedure_code=procedure_code,
            filler_id=filler_id,
            commit=True,
            allow_existing_results=(
                allow_existing_results
            ),
        )
        committed = invoke_receiver(
            commit_source,
            container=container,
        )

        if committed.get("status") != "COMMIT_PASSED":
            raise RuntimeError(
                "OpenEMR ORU commit did not pass: "
                f"{committed}"
            )

    return OpenEmrIngestion(
        dry_run=dry_run,
        committed=committed,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or locally commit an ORU scenario "
            "through OpenEMR's native DORN parser."
        )
    )
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--order-id", type=int, required=True)
    parser.add_argument("--patient-id", type=int, required=True)
    parser.add_argument("--encounter-id", type=int, required=True)
    parser.add_argument("--lab-id", type=int, required=True)
    parser.add_argument(
        "--container",
        default=DEFAULT_OPENEMR_CONTAINER,
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist the result after a successful dry run.",
    )
    parser.add_argument(
        "--confirm-order-id",
        type=int,
        help=(
            "Required with --commit; must equal --order-id."
        ),
    )
    parser.add_argument(
        "--allow-existing-results",
        action="store_true",
        help=(
            "Allow an explicitly intended lifecycle update "
            "to an order that already has results."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = OpenEmrTarget(
        order_id=args.order_id,
        patient_id=args.patient_id,
        encounter_id=args.encounter_id,
        lab_id=args.lab_id,
    )

    try:
        result = execute_openemr_scenario(
            args.scenario,
            target,
            commit=args.commit,
            confirm_order_id=args.confirm_order_id,
            allow_existing_results=(
                args.allow_existing_results
            ),
            container=args.container,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print()
        print(f"OPENEMR ORU INGESTION: FAIL - {exc}")
        return 1

    print()
    print("OPENEMR ORU INGESTION")
    print("----------------------")
    print(f"Order ID:  {target.order_id}")
    print(f"Dry run:   {result.dry_run['status']}")

    if result.committed is None:
        print("Commit:    NOT REQUESTED")
    else:
        print(f"Commit:    {result.committed['status']}")
        persisted = result.committed["persisted"]
        print(
            "Result:    "
            f"{persisted['result_text']} "
            f"{persisted['result']} "
            f"{persisted['units']}"
        )
        print(
            "Review:    "
            f"{persisted['review_status']}"
        )

    print("OPENEMR ORU INGESTION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

