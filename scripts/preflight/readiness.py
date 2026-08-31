from dataclasses import dataclass
import json
from pathlib import Path
import socket
import subprocess
import tempfile

from scripts.dicom.pacs_destination_health import (
    build_destination_health_report,
)
from scripts.fhir.auth_probe import get_token_lifecycle


EXPECTED_CONTAINERS = (
    "health-it-openemr-lab-openemr-1",
    "health-it-openemr-lab-mysql-1",
    "health-it-mirth-lab-interop-db-1",
    "health-it-mirth-lab-mirth-1",
    "health-it-orthanc-lab-orthanc-1",
    "health-it-mirth-lab-mirth-db-1",
)

HEALTH_REQUIRED = {
    "health-it-openemr-lab-openemr-1",
    "health-it-openemr-lab-mysql-1",
    "health-it-mirth-lab-interop-db-1",
    "health-it-mirth-lab-mirth-db-1",
}

REQUIRED_OPENEMR_ENV_KEYS = {
    "OPENEMR_DB_ROOT_PASSWORD",
    "OPENEMR_DB_USER",
    "OPENEMR_DB_PASSWORD",
    "OPENEMR_ADMIN_USER",
    "OPENEMR_ADMIN_PASSWORD",
}

DEFAULT_TOKEN_FILE = (
    Path(tempfile.gettempdir())
    / "openemr-fhir-token.json"
)

RESTRICTED_TOKEN_FILE = (
    Path(tempfile.gettempdir())
    / "openemr-fhir-restricted-token.json"
)


@dataclass(frozen=True)
class CheckResult:
    component: str
    ready: bool
    detail: str

    @property
    def state(self) -> str:
        return "READY" if self.ready else "NOT_READY"


def check_environment_file(
    env_path: Path = Path(".env"),
) -> CheckResult:
    component = "OPENEMR_ENV"

    if not env_path.exists():
        return CheckResult(
            component,
            False,
            f"Environment file not found: {env_path}",
        )

    configured_keys = set()

    for raw_line in env_path.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if separator and key.strip() and value.strip():
            configured_keys.add(key.strip())

    missing_keys = REQUIRED_OPENEMR_ENV_KEYS - configured_keys

    if missing_keys:
        return CheckResult(
            component,
            False,
            "Missing or blank variables: "
            + ", ".join(sorted(missing_keys)),
        )

    return CheckResult(
        component,
        True,
        "Required OpenEMR variables are configured",
    )


def inspect_container_state(container_name: str) -> dict:
    completed = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{json .State}}",
            container_name,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    if completed.returncode != 0:
        error = completed.stderr.strip() or "docker inspect failed"
        raise RuntimeError(error)

    return json.loads(completed.stdout)


def evaluate_container_state(
    container_name: str,
    state: dict,
) -> CheckResult:
    component = f"CONTAINER:{container_name}"

    if not state.get("Running", False):
        return CheckResult(
            component,
            False,
            f"Container state is {state.get('Status', 'unknown')}",
        )

    if container_name in HEALTH_REQUIRED:
        health_status = (
            state.get("Health", {}).get("Status")
        )

        if health_status != "healthy":
            return CheckResult(
                component,
                False,
                f"Container health is {health_status or 'unavailable'}",
            )

    return CheckResult(
        component,
        True,
        "Container is running and satisfies its health contract",
    )


def check_container(container_name: str) -> CheckResult:
    try:
        state = inspect_container_state(container_name)
    except (
        OSError,
        json.JSONDecodeError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        return CheckResult(
            f"CONTAINER:{container_name}",
            False,
            f"Unable to inspect container: {exc}",
        )

    return evaluate_container_state(container_name, state)


def check_token(
    component: str,
    token_file: Path,
    *,
    minimum_remaining_seconds: int = 300,
) -> CheckResult:
    try:
        lifecycle = get_token_lifecycle(
            warning_threshold_seconds=(
                minimum_remaining_seconds
            ),
            token_file=token_file,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return CheckResult(
            component,
            False,
            f"Token prerequisite failed: {exc}",
        )

    if lifecycle["state"] != "FRESH":
        return CheckResult(
            component,
            False,
            "Token state is "
            f"{lifecycle['state']} with "
            f"{lifecycle['remaining_seconds']} seconds remaining",
        )

    return CheckResult(
        component,
        True,
        "Fresh token with "
        f"{lifecycle['remaining_seconds']} seconds remaining",
    )


def check_tcp_listener(
    *,
    host: str = "127.0.0.1",
    port: int = 11112,
    timeout_seconds: float = 2.0,
) -> CheckResult:
    component = "INTEROPLAB_SCP"

    try:
        with socket.create_connection(
            (host, port),
            timeout=timeout_seconds,
        ):
            pass
    except OSError as exc:
        return CheckResult(
            component,
            False,
            f"TCP {host}:{port} is unavailable: {exc}",
        )

    return CheckResult(
        component,
        True,
        f"TCP {host}:{port} is accepting connections",
    )


def evaluate_pacs_report(report: dict) -> CheckResult:
    component = "ORTHANC_INTEROPLAB"

    destination = next(
        (
            item
            for item in report.get("destinations", [])
            if item.get("name", "").lower() == "interoplab"
        ),
        None,
    )

    if destination is None:
        return CheckResult(
            component,
            False,
            "Orthanc modality interoplab is not configured",
        )

    if not destination.get("healthy", False):
        return CheckResult(
            component,
            False,
            "Orthanc C-ECHO to INTEROPLAB failed",
        )

    return CheckResult(
        component,
        True,
        "Orthanc C-ECHO to INTEROPLAB succeeded",
    )


def check_pacs_destination() -> CheckResult:
    try:
        report = build_destination_health_report()
    except (OSError, ValueError, RuntimeError) as exc:
        return CheckResult(
            "ORTHANC_INTEROPLAB",
            False,
            f"Unable to build PACS health report: {exc}",
        )

    return evaluate_pacs_report(report)


def run_preflight() -> list[CheckResult]:
    results = [check_environment_file()]

    results.extend(
        check_container(container_name)
        for container_name in EXPECTED_CONTAINERS
    )

    results.extend(
        [
            check_token(
                "FHIR_ADMIN_TOKEN",
                DEFAULT_TOKEN_FILE,
            ),
            check_token(
                "FHIR_RESTRICTED_TOKEN",
                RESTRICTED_TOKEN_FILE,
            ),
            check_tcp_listener(),
            check_pacs_destination(),
        ]
    )

    return results


def print_report(results: list[CheckResult]) -> None:
    print()
    print("INTEROPERABILITY RUNTIME READINESS")
    print("----------------------------------")

    for result in results:
        print(
            f"{result.component:<48} "
            f"{result.state:<10} "
            f"{result.detail}"
        )

    overall_ready = all(result.ready for result in results)

    print()
    print(
        "RUNTIME READINESS: "
        f"{'PASS' if overall_ready else 'FAIL'}"
    )


def main() -> int:
    results = run_preflight()
    print_report(results)

    return 0 if all(result.ready for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
