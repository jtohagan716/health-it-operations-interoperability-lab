import json
from pathlib import Path


REQUIRED_ROOT_PATHS = (
    "scenario_id",
    "message.timestamp",
    "message.control_id",
    "patient.identifier",
    "patient.family_name",
    "patient.given_name",
    "patient.date_of_birth",
    "patient.administrative_sex",
    "order.placer_number",
    "order.filler_number",
    "order.service_code",
    "order.service_display",
    "order.observation_timestamp",
    "order.result_status",
    "expected.ack_code",
)

REQUIRED_OBSERVATION_FIELDS = (
    "value_type",
    "code",
    "display",
    "value",
    "units",
    "reference_range",
    "abnormal_flag",
    "result_status",
)


def get_path(payload: dict, dotted_path: str):
    value = payload

    for component in dotted_path.split("."):
        if not isinstance(value, dict) or component not in value:
            raise ValueError(
                f"Scenario field is missing: {dotted_path}"
            )
        value = value[component]

    return value


def observations_for_scenario(scenario: dict) -> list[dict]:
    has_singular = "observation" in scenario
    has_plural = "observations" in scenario

    if has_singular == has_plural:
        raise ValueError(
            "Scenario must define exactly one of observation or "
            "observations."
        )

    observations = (
        [scenario["observation"]]
        if has_singular
        else scenario["observations"]
    )

    if not isinstance(observations, list) or not observations:
        raise ValueError(
            "Scenario observations must be a non-empty list."
        )

    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict):
            raise ValueError(
                f"Scenario observation {index} must be an object."
            )

    return observations


def validate_scenario(scenario: dict) -> None:
    for dotted_path in REQUIRED_ROOT_PATHS:
        value = get_path(scenario, dotted_path)

        if value is None or value == "":
            raise ValueError(
                f"Scenario field is blank: {dotted_path}"
            )

    observations = observations_for_scenario(scenario)

    for index, observation in enumerate(observations, start=1):
        location = (
            "observation"
            if "observation" in scenario
            else f"observations[{index - 1}]"
        )
        for field in REQUIRED_OBSERVATION_FIELDS:
            if field not in observation:
                raise ValueError(
                    "Scenario field is missing: "
                    f"{location}.{field}"
                )
            if observation[field] is None or observation[field] == "":
                raise ValueError(
                    "Scenario field is blank: "
                    f"{location}.{field}"
                )

    if scenario["expected"]["ack_code"] not in {"AA", "AE", "AR"}:
        raise ValueError(
            "expected.ack_code must be AA, AE, or AR."
        )


def load_scenario(path: Path | str) -> dict:
    path = Path(path)

    try:
        scenario = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid scenario JSON in {path}: {exc}"
        ) from exc

    if not isinstance(scenario, dict):
        raise ValueError("HL7 scenario must be a JSON object.")

    validate_scenario(scenario)
    return scenario


def build_oru_segments(
    scenario: dict,
    *,
    message_control_id: str | None = None,
) -> list[str]:
    validate_scenario(scenario)

    message = scenario["message"]
    patient = scenario["patient"]
    order = scenario["order"]
    observations = observations_for_scenario(scenario)
    control_id = message_control_id or message["control_id"]

    msh_fields = [
        "MSH", "^~\\&",
        message.get("sending_application", "LABSYSTEM"),
        message.get("sending_facility", "INTEROPLAB"),
        "MIRTH", "INTEROPLAB", message["timestamp"], "",
        "ORU^R01^ORU_R01", control_id, "P", "2.5.1",
    ]
    pid_fields = [
        "PID", "1", "",
        f"{patient['identifier']}^^^INTEROPLAB^MR", "",
        f"{patient['family_name']}^{patient['given_name']}^^^^^L",
        "", patient["date_of_birth"], patient["administrative_sex"],
    ]
    obr_fields = [""] * 26
    obr_fields[0] = "OBR"
    obr_fields[1] = "1"
    obr_fields[2] = order["placer_number"]
    obr_fields[3] = order["filler_number"]
    obr_fields[4] = (
        f"{order['service_code']}^{order['service_display']}^"
        f"{order.get('coding_system', 'LN')}"
    )
    obr_fields[7] = order["observation_timestamp"]
    obr_fields[25] = order["result_status"]

    obx_segments = []
    for sequence, observation in enumerate(observations, start=1):
        obx_fields = [""] * 12
        obx_fields[0] = "OBX"
        obx_fields[1] = str(sequence)
        obx_fields[2] = observation["value_type"]
        obx_fields[3] = (
            f"{observation['code']}^{observation['display']}^"
            f"{observation.get('coding_system', 'LN')}"
        )
        obx_fields[5] = str(observation["value"])
        obx_fields[6] = observation["units"]
        obx_fields[7] = observation["reference_range"]
        obx_fields[8] = observation["abnormal_flag"]
        obx_fields[11] = observation["result_status"]
        obx_segments.append("|".join(obx_fields))

    return [
        "|".join(msh_fields),
        "|".join(pid_fields),
        "|".join(obr_fields),
        *obx_segments,
    ]


def expected_observations(scenario: dict) -> list[dict]:
    validate_scenario(scenario)
    return [
        {
            "observation_code": observation["code"],
            "observation_value": str(observation["value"]),
            "units": observation["units"],
            "reference_range": observation["reference_range"],
            "abnormal_flag": observation["abnormal_flag"],
            "result_status": observation["result_status"],
        }
        for observation in observations_for_scenario(scenario)
    ]


def expected_semantics(scenario: dict) -> dict:
    """Return the legacy flat contract for one-observation scenarios."""
    observations = expected_observations(scenario)
    if len(observations) != 1:
        raise ValueError(
            "expected_semantics supports one observation; use "
            "expected_observations for panel scenarios."
        )

    return {
        "patient_identifier": scenario["patient"]["identifier"],
        "placer_order_number": scenario["order"]["placer_number"],
        "filler_order_number": scenario["order"]["filler_number"],
        "service_code": scenario["order"]["service_code"],
        **observations[0],
    }
