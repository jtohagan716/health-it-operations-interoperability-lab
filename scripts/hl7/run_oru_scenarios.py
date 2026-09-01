import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from scripts.hl7.oru_scenario import (
    build_oru_segments,
    expected_semantics,
    load_scenario,
)
from scripts.hl7.scenario_runtime import (
    Acknowledgment,
    generate_control_id,
    run_psql,
    send_segments,
)


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 6662
DEFAULT_POLL_TIMEOUT = 10.0
DEFAULT_POLL_INTERVAL = 0.25


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    message_control_id: str
    acknowledgment: Acknowledgment
    persisted: dict | None


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def get_accepted_observation(
    message_control_id: str,
) -> dict | None:
    output = run_psql(
        f"""
        SELECT
            m.patient_identifier,
            m.placer_order_number,
            m.filler_order_number,
            m.service_code,
            m.processing_status,
            o.observation_code,
            o.observation_value,
            o.units,
            o.reference_range,
            o.abnormal_flag,
            o.result_status
        FROM audit.oru_messages m
        JOIN audit.oru_observations o
            ON o.oru_message_id = m.oru_message_id
        WHERE m.message_control_id = {
            sql_literal(message_control_id)
        }
        ORDER BY m.received_at DESC
        LIMIT 1;
        """
    )

    if not output:
        return None

    fields = output.split("|")

    if len(fields) != 11:
        raise RuntimeError(
            "Unexpected accepted ORU persistence row: "
            f"{output}"
        )

    return {
        "patient_identifier": fields[0],
        "placer_order_number": fields[1],
        "filler_order_number": fields[2],
        "service_code": fields[3],
        "processing_status": fields[4],
        "observation_code": fields[5],
        "observation_value": fields[6],
        "units": fields[7],
        "reference_range": fields[8],
        "abnormal_flag": fields[9],
        "result_status": fields[10],
    }


def wait_for_accepted_observation(
    message_control_id: str,
    *,
    timeout: float = DEFAULT_POLL_TIMEOUT,
    interval: float = DEFAULT_POLL_INTERVAL,
) -> dict:
    if timeout <= 0:
        raise ValueError("Poll timeout must be positive.")

    if interval <= 0:
        raise ValueError("Poll interval must be positive.")

    deadline = time.monotonic() + timeout

    while True:
        persisted = get_accepted_observation(
            message_control_id
        )

        if persisted is not None:
            return persisted

        if time.monotonic() >= deadline:
            raise RuntimeError(
                "Accepted ORU persistence was not found within "
                f"{timeout:.2f} seconds for "
                f"MSH-10 {message_control_id}."
            )

        time.sleep(interval)


def assert_persisted_semantics(
    scenario: dict,
    persisted: dict,
) -> None:
    expected = expected_semantics(scenario)
    observed = {
        key: persisted[key]
        for key in expected
    }

    if observed != expected:
        differences = [
            (
                f"{key}: expected {expected[key]!r}, "
                f"observed {observed[key]!r}"
            )
            for key in expected
            if observed[key] != expected[key]
        ]

        raise RuntimeError(
            "Persisted ORU semantics did not match the "
            "scenario contract: "
            + "; ".join(differences)
        )

    if persisted["processing_status"] != "ACCEPTED":
        raise RuntimeError(
            "Expected processing_status ACCEPTED, received "
            f"{persisted['processing_status']!r}."
        )


def execute_scenario(
    scenario_path: Path | str,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    poll_timeout: float = DEFAULT_POLL_TIMEOUT,
) -> ScenarioResult:
    scenario = load_scenario(scenario_path)
    control_id = generate_control_id(
        scenario["scenario_id"].upper(),
        suffix_length=10,
    )
    segments = build_oru_segments(
        scenario,
        message_control_id=control_id,
    )
    acknowledgment = send_segments(
        segments,
        host=host,
        port=port,
    )
    expected_ack = scenario["expected"]["ack_code"]

    if acknowledgment.code != expected_ack:
        raise RuntimeError(
            f"Scenario {scenario['scenario_id']} expected "
            f"ACK {expected_ack}, received "
            f"{acknowledgment.code}."
        )

    persisted = None

    if acknowledgment.accepted:
        persisted = wait_for_accepted_observation(
            control_id,
            timeout=poll_timeout,
        )
        assert_persisted_semantics(
            scenario,
            persisted,
        )

    return ScenarioResult(
        scenario_id=scenario["scenario_id"],
        message_control_id=control_id,
        acknowledgment=acknowledgment,
        persisted=persisted,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute data-driven ORU scenarios through Mirth "
            "and reconcile accepted results with PostgreSQL."
        )
    )
    parser.add_argument(
        "scenarios",
        nargs="+",
        type=Path,
        help="One or more ORU scenario JSON files.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=DEFAULT_POLL_TIMEOUT,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print()
    print("ORU SCENARIO VALIDATION")
    print("-----------------------")

    try:
        for scenario_path in args.scenarios:
            result = execute_scenario(
                scenario_path,
                host=args.host,
                port=args.port,
                poll_timeout=args.poll_timeout,
            )

            print()
            print(f"Scenario:  {result.scenario_id}")
            print(f"MSH-10:    {result.message_control_id}")
            print(f"ACK:       {result.acknowledgment.code}")
            print(
                "Round trip: "
                f"{result.acknowledgment.round_trip_seconds * 1000:.2f} ms"
            )
            print(
                "Persistence: "
                + (
                    "VERIFIED"
                    if result.persisted is not None
                    else "NOT EXPECTED"
                )
            )

    except (OSError, RuntimeError, ValueError) as exc:
        print()
        print(f"ORU SCENARIO VALIDATION: FAIL - {exc}")
        return 1

    print()
    print("ORU SCENARIO VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
