import json
from pathlib import Path


REQUIRED_PATHS = (
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
    "observation.value_type",
    "observation.code",
    "observation.display",
    "observation.value",
    "observation.units",
    "observation.reference_range",
    "observation.abnormal_flag",
    "observation.result_status",
    "expected.ack_code",
)


def get_path(
    payload: dict,
    dotted_path: str,
):
    value = payload

    for component in dotted_path.split("."):
        if not isinstance(value, dict):
            raise ValueError(
                f"Scenario field is missing: {dotted_path}"
            )

        if component not in value:
            raise ValueError(
                f"Scenario field is missing: {dotted_path}"
            )

        value = value[component]

    return value


def validate_scenario(scenario: dict) -> None:
    for dotted_path in REQUIRED_PATHS:
        value = get_path(
            scenario,
            dotted_path,
        )

        if value is None or value == "":
            raise ValueError(
                f"Scenario field is blank: {dotted_path}"
            )

    if scenario["expected"]["ack_code"] not in {
        "AA",
        "AE",
        "AR",
    }:
        raise ValueError(
            "expected.ack_code must be AA, AE, or AR."
        )


def load_scenario(path: Path | str) -> dict:
    path = Path(path)

    try:
        scenario = json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid scenario JSON in {path}: {exc}"
        ) from exc

    if not isinstance(scenario, dict):
        raise ValueError(
            "HL7 scenario must be a JSON object."
        )

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
    observation = scenario["observation"]

    control_id = (
        message_control_id
        or message["control_id"]
    )

    msh_fields = [
        "MSH",
        "^~\\&",
        message.get(
            "sending_application",
            "LABSYSTEM",
        ),
        message.get(
            "sending_facility",
            "INTEROPLAB",
        ),
        "MIRTH",
        "INTEROPLAB",
        message["timestamp"],
        "",
        "ORU^R01^ORU_R01",
        control_id,
        "P",
        "2.5.1",
    ]

    pid_fields = [
        "PID",
        "1",
        "",
        (
            f"{patient['identifier']}"
            "^^^INTEROPLAB^MR"
        ),
        "",
        (
            f"{patient['family_name']}^"
            f"{patient['given_name']}^^^^^L"
        ),
        "",
        patient["date_of_birth"],
        patient["administrative_sex"],
    ]

    obr_fields = [""] * 26
    obr_fields[0] = "OBR"
    obr_fields[1] = "1"
    obr_fields[2] = order["placer_number"]
    obr_fields[3] = order["filler_number"]
    obr_fields[4] = (
        f"{order['service_code']}^"
        f"{order['service_display']}^LN"
    )
    obr_fields[7] = order[
        "observation_timestamp"
    ]
    obr_fields[25] = order["result_status"]

    obx_fields = [""] * 12
    obx_fields[0] = "OBX"
    obx_fields[1] = "1"
    obx_fields[2] = observation["value_type"]
    obx_fields[3] = (
        f"{observation['code']}^"
        f"{observation['display']}^LN"
    )
    obx_fields[5] = str(observation["value"])
    obx_fields[6] = observation["units"]
    obx_fields[7] = observation[
        "reference_range"
    ]
    obx_fields[8] = observation["abnormal_flag"]
    obx_fields[11] = observation["result_status"]

    return [
        "|".join(msh_fields),
        "|".join(pid_fields),
        "|".join(obr_fields),
        "|".join(obx_fields),
    ]


def expected_semantics(scenario: dict) -> dict:
    validate_scenario(scenario)

    return {
        "patient_identifier": scenario[
            "patient"
        ]["identifier"],
        "placer_order_number": scenario[
            "order"
        ]["placer_number"],
        "filler_order_number": scenario[
            "order"
        ]["filler_number"],
        "service_code": scenario[
            "order"
        ]["service_code"],
        "observation_code": scenario[
            "observation"
        ]["code"],
        "observation_value": str(
            scenario["observation"]["value"]
        ),
        "units": scenario[
            "observation"
        ]["units"],
        "reference_range": scenario[
            "observation"
        ]["reference_range"],
        "abnormal_flag": scenario[
            "observation"
        ]["abnormal_flag"],
        "result_status": scenario[
            "observation"
        ]["result_status"],
    }
