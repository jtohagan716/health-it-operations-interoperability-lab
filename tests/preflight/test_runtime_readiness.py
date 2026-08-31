from scripts.preflight import readiness


def test_environment_file_requires_nonblank_keys(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            f"{key}=configured"
            for key in readiness.REQUIRED_OPENEMR_ENV_KEYS
        ),
        encoding="utf-8",
    )

    result = readiness.check_environment_file(env_path)

    assert result.ready is True
    assert result.state == "READY"


def test_environment_file_reports_missing_keys(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENEMR_DB_USER=configured\n",
        encoding="utf-8",
    )

    result = readiness.check_environment_file(env_path)

    assert result.ready is False
    assert "OPENEMR_ADMIN_USER" in result.detail


def test_healthy_container_satisfies_contract():
    result = readiness.evaluate_container_state(
        "health-it-openemr-lab-openemr-1",
        {
            "Running": True,
            "Status": "running",
            "Health": {"Status": "healthy"},
        },
    )

    assert result.ready is True


def test_unhealthy_container_fails_contract():
    result = readiness.evaluate_container_state(
        "health-it-openemr-lab-openemr-1",
        {
            "Running": True,
            "Status": "running",
            "Health": {"Status": "starting"},
        },
    )

    assert result.ready is False
    assert "starting" in result.detail


def test_token_check_uses_selected_role_file(
    monkeypatch,
    tmp_path,
):
    selected_token_file = tmp_path / "restricted-token.json"
    observed = {}

    def fake_lifecycle(**kwargs):
        observed.update(kwargs)
        return {
            "state": "FRESH",
            "remaining_seconds": 1800,
        }

    monkeypatch.setattr(
        readiness,
        "get_token_lifecycle",
        fake_lifecycle,
    )

    result = readiness.check_token(
        "FHIR_RESTRICTED_TOKEN",
        selected_token_file,
    )

    assert result.ready is True
    assert observed["token_file"] == selected_token_file


def test_expired_token_fails_readiness(monkeypatch, tmp_path):
    monkeypatch.setattr(
        readiness,
        "get_token_lifecycle",
        lambda **kwargs: {
            "state": "EXPIRED",
            "remaining_seconds": -10,
        },
    )

    result = readiness.check_token(
        "FHIR_ADMIN_TOKEN",
        tmp_path / "expired-token.json",
    )

    assert result.ready is False
    assert "EXPIRED" in result.detail


def test_interoplab_destination_is_required():
    result = readiness.evaluate_pacs_report(
        {
            "destinations": [
                {
                    "name": "interoplab",
                    "healthy": True,
                },
                {
                    "name": "unavailable",
                    "healthy": False,
                },
            ]
        }
    )

    assert result.ready is True


def test_unavailable_negative_control_does_not_fail_preflight():
    result = readiness.evaluate_pacs_report(
        {
            "overall": "DEGRADED",
            "destinations": [
                {
                    "name": "interoplab",
                    "healthy": True,
                },
                {
                    "name": "unavailable",
                    "healthy": False,
                },
            ],
        }
    )

    assert result.ready is True


def test_environment_secret_values_are_not_printed(
    tmp_path,
    capsys,
):
    secret = "synthetic-secret-must-not-appear"
    env_path = tmp_path / ".env"

    env_path.write_text(
        "\n".join(
            f"{key}={secret}"
            for key in readiness.REQUIRED_OPENEMR_ENV_KEYS
        ),
        encoding="utf-8",
    )

    result = readiness.check_environment_file(
        env_path
    )

    readiness.print_report([result])

    output = capsys.readouterr().out

    assert result.ready is True
    assert secret not in output
    assert "RUNTIME READINESS: PASS" in output

def test_main_returns_zero_when_all_checks_are_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        readiness,
        "run_preflight",
        lambda: [
            readiness.CheckResult(
                "SYNTHETIC_READY_COMPONENT",
                True,
                "Ready for testing",
            )
        ],
    )

    assert readiness.main() == 0

def test_main_returns_one_when_any_check_is_not_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        readiness,
        "run_preflight",
        lambda: [
            readiness.CheckResult(
                "SYNTHETIC_READY_COMPONENT",
                True,
                "Ready for testing",
            ),
            readiness.CheckResult(
                "SYNTHETIC_FAILED_COMPONENT",
                False,
                "Dependency unavailable",
            ),
        ],
    )

    assert readiness.main() == 1
