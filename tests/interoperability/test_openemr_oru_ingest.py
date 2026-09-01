import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.hl7.openemr_oru_ingest import (
    OpenEmrTarget,
    build_openemr_oru_segments,
    execute_openemr_scenario,
    invoke_receiver,
    render_receiver,
)
from scripts.hl7.oru_scenario import load_scenario


SCENARIO_PATH = Path(
    "fixtures/hl7/oru/scenarios/normal-glucose-final.json"
)
TARGET = OpenEmrTarget(
    order_id=3,
    patient_id=1,
    encounter_id=6,
    lab_id=2,
)


def fields(segments: list[str], name: str) -> list[str]:
    return next(
        segment.split("|")
        for segment in segments
        if segment.startswith(f"{name}|")
    )


def test_openemr_message_reverses_dorn_routing():
    scenario = load_scenario(SCENARIO_PATH)
    segments = build_openemr_oru_segments(
        scenario,
        TARGET,
        message_control_id="OPENEMR-CONTROL-1",
        filler_id="FILLER-1",
        commit=False,
    )

    msh = fields(segments, "MSH")

    assert msh[2:6] == [
        "DORN",
        "LAB",
        "OEMR",
        "INTEROPLAB",
    ]
    assert msh[9] == "OPENEMR-CONTROL-1"


def test_openemr_message_correlates_order_and_encounter():
    scenario = load_scenario(SCENARIO_PATH)
    segments = build_openemr_oru_segments(
        scenario,
        TARGET,
        message_control_id="OPENEMR-CONTROL-1",
        filler_id="FILLER-1",
        commit=False,
    )

    pv1 = fields(segments, "PV1")
    orc = fields(segments, "ORC")
    obr = fields(segments, "OBR")

    assert pv1[19] == "6"
    assert orc[1:3] == ["RE", "3"]
    assert obr[2] == "3"
    assert obr[4] == "2345-7^Glucose^LN"
    assert obr[22] == scenario["order"][
        "observation_timestamp"
    ]


def test_dry_run_blanks_filler_to_prevent_side_effect():
    scenario = load_scenario(SCENARIO_PATH)
    segments = build_openemr_oru_segments(
        scenario,
        TARGET,
        message_control_id="OPENEMR-CONTROL-1",
        filler_id="FILLER-1",
        commit=False,
    )

    assert fields(segments, "OBR")[3] == ""


def test_commit_includes_filler_for_correlation():
    scenario = load_scenario(SCENARIO_PATH)
    segments = build_openemr_oru_segments(
        scenario,
        TARGET,
        message_control_id="OPENEMR-CONTROL-1",
        filler_id="FILLER-1",
        commit=True,
    )

    assert fields(segments, "OBR")[3] == "FILLER-1"


def test_openemr_message_populates_observation_datetime():
    scenario = load_scenario(SCENARIO_PATH)
    segments = build_openemr_oru_segments(
        scenario,
        TARGET,
        message_control_id="OPENEMR-CONTROL-1",
        filler_id="FILLER-1",
        commit=False,
    )

    assert fields(segments, "OBX")[14] == scenario[
        "order"
    ]["observation_timestamp"]


def test_render_receiver_base64_encodes_payload():
    template = (
        "__OPENEMR_ORDER_ID__|"
        "__OPENEMR_PATIENT_ID__|"
        "__OPENEMR_ENCOUNTER_ID__|"
        "__OPENEMR_LAB_ID__|"
        "__OPENEMR_COMMIT__|"
        "__OPENEMR_ALLOW_EXISTING__|"
        "__OPENEMR_PROCEDURE_CODE_BASE64__|"
        "__OPENEMR_FILLER_ID_BASE64__|"
        "__OPENEMR_HL7_BASE64__"
    )
    rendered = render_receiver(
        template,
        segments=["MSH|^~\\&|DORN"],
        target=TARGET,
        procedure_code="2345-7",
        filler_id="FILLER-'SAFE'",
        commit=False,
        allow_existing_results=False,
    )

    parts = rendered.split("|")

    assert parts[:6] == ["3", "1", "6", "2", "false", "false"]
    assert base64.b64decode(parts[6]).decode() == "2345-7"
    assert base64.b64decode(parts[7]).decode() == "FILLER-'SAFE'"
    assert base64.b64decode(parts[8]).decode().endswith("\r")


def test_invoke_receiver_uses_apache_and_parses_json(
    monkeypatch,
):
    completed = SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"status": "DRY_RUN_PASSED"}),
        stderr="",
    )
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return completed

    monkeypatch.setattr(
        "scripts.hl7.openemr_oru_ingest.subprocess.run",
        fake_run,
    )

    payload = invoke_receiver("<?php", container="openemr-test")

    assert payload["status"] == "DRY_RUN_PASSED"
    assert observed["command"] == [
        "docker",
        "exec",
        "-i",
        "--user",
        "apache",
        "openemr-test",
        "php",
    ]
    assert observed["kwargs"]["input"] == "<?php"


def test_commit_requires_matching_confirmation():
    with pytest.raises(
        ValueError,
        match="confirm-order-id",
    ):
        execute_openemr_scenario(
            SCENARIO_PATH,
            TARGET,
            commit=True,
            confirm_order_id=99,
        )


def test_execution_always_dry_runs_before_commit(
    monkeypatch,
    tmp_path: Path,
):
    template = tmp_path / "receiver.php"
    template.write_text(
        "|".join(
            [
                "__OPENEMR_ORDER_ID__",
                "__OPENEMR_PATIENT_ID__",
                "__OPENEMR_ENCOUNTER_ID__",
                "__OPENEMR_LAB_ID__",
                "__OPENEMR_COMMIT__",
                "__OPENEMR_ALLOW_EXISTING__",
                "__OPENEMR_PROCEDURE_CODE_BASE64__",
                "__OPENEMR_FILLER_ID_BASE64__",
                "__OPENEMR_HL7_BASE64__",
            ]
        ),
        encoding="utf-8",
    )
    responses = iter(
        [
            {"status": "DRY_RUN_PASSED"},
            {
                "status": "COMMIT_PASSED",
                "persisted": {},
            },
        ]
    )
    calls = []

    def fake_invoke(source, *, container):
        calls.append(source)
        return next(responses)

    monkeypatch.setattr(
        "scripts.hl7.openemr_oru_ingest.invoke_receiver",
        fake_invoke,
    )

    result = execute_openemr_scenario(
        SCENARIO_PATH,
        TARGET,
        commit=True,
        confirm_order_id=3,
        receiver_template=template,
    )

    assert result.dry_run["status"] == "DRY_RUN_PASSED"
    assert result.committed["status"] == "COMMIT_PASSED"
    assert len(calls) == 2
    assert "|false|false|" in calls[0]
    assert "|true|false|" in calls[1]

