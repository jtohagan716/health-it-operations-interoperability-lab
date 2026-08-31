from datetime import datetime, timedelta, timezone

import pytest
import json

from scripts.fhir import auth_probe


def test_fresh_token_is_classified_as_fresh(monkeypatch):
    now = datetime.now(timezone.utc)

    fake_token_data = {
        "access_token": "synthetic-test-token",
        "token_type": "Bearer",
        "scope": "user/Patient.rs",
        "expires_in": 3600,
        "acquired_at_utc": now.isoformat(),
        "expires_at_utc": (
            now + timedelta(minutes=30)
        ).isoformat(),
    }

    monkeypatch.setattr(
        auth_probe,
        "load_token_data",
        lambda: fake_token_data,
    )

    lifecycle = auth_probe.get_token_lifecycle(
        warning_threshold_seconds=300
    )

    assert lifecycle["state"] == "FRESH"
    assert lifecycle["remaining_seconds"] > 300


def test_expiring_soon_token_is_detected(monkeypatch):
    now = datetime.now(timezone.utc)

    fake_token_data = {
        "access_token": "synthetic-test-token",
        "token_type": "Bearer",
        "scope": "user/Patient.rs",
        "expires_in": 3600,
        "acquired_at_utc": (
            now - timedelta(minutes=59)
        ).isoformat(),
        "expires_at_utc": (
            now + timedelta(seconds=120)
        ).isoformat(),
    }

    monkeypatch.setattr(
        auth_probe,
        "load_token_data",
        lambda: fake_token_data,
    )

    lifecycle = auth_probe.get_token_lifecycle(
        warning_threshold_seconds=300
    )

    assert lifecycle["state"] == "EXPIRING_SOON"
    assert 0 < lifecycle["remaining_seconds"] <= 300


def test_expired_token_is_detected(monkeypatch):
    now = datetime.now(timezone.utc)

    fake_token_data = {
        "access_token": "synthetic-test-token",
        "token_type": "Bearer",
        "scope": "user/Patient.rs",
        "expires_in": 3600,
        "acquired_at_utc": (
            now - timedelta(hours=2)
        ).isoformat(),
        "expires_at_utc": (
            now - timedelta(seconds=30)
        ).isoformat(),
    }

    monkeypatch.setattr(
        auth_probe,
        "load_token_data",
        lambda: fake_token_data,
    )

    lifecycle = auth_probe.get_token_lifecycle(
        warning_threshold_seconds=300
    )

    assert lifecycle["state"] == "EXPIRED"
    assert lifecycle["remaining_seconds"] <= 0


def test_expiring_soon_token_is_rejected_as_test_prerequisite(
    monkeypatch,
):
    now = datetime.now(timezone.utc)

    fake_token_data = {
        "access_token": "synthetic-test-token",
        "token_type": "Bearer",
        "scope": "user/Patient.rs",
        "expires_in": 3600,
        "acquired_at_utc": (
            now - timedelta(minutes=59)
        ).isoformat(),
        "expires_at_utc": (
            now + timedelta(seconds=120)
        ).isoformat(),
    }

    monkeypatch.setattr(
        auth_probe,
        "load_token_data",
        lambda: fake_token_data,
    )

    with pytest.raises(
        RuntimeError,
        match="only .* seconds remaining",
    ):
        auth_probe.require_fresh_access_token(
            minimum_remaining_seconds=300
        )


def test_expired_token_is_rejected_as_test_prerequisite(
    monkeypatch,
):
    now = datetime.now(timezone.utc)

    fake_token_data = {
        "access_token": "synthetic-test-token",
        "token_type": "Bearer",
        "scope": "user/Patient.rs",
        "expires_in": 3600,
        "acquired_at_utc": (
            now - timedelta(hours=2)
        ).isoformat(),
        "expires_at_utc": (
            now - timedelta(seconds=30)
        ).isoformat(),
    }

    monkeypatch.setattr(
        auth_probe,
        "load_token_data",
        lambda: fake_token_data,
    )

    with pytest.raises(
        RuntimeError,
        match="access token has expired",
    ):
        auth_probe.require_fresh_access_token()

def test_explicit_token_file_is_used(tmp_path):
    now = datetime.now(timezone.utc)

    selected_token_file = (
        tmp_path / "role-specific-token.json"
    )

    selected_token_data = {
        "access_token": "selected-role-token",
        "token_type": "Bearer",
        "scope": "user/Patient.rs",
        "expires_in": 3600,
        "acquired_at_utc": now.isoformat(),
        "expires_at_utc": (
            now + timedelta(minutes=30)
        ).isoformat(),
    }

    selected_token_file.write_text(
        json.dumps(selected_token_data),
        encoding="utf-8",
    )

    access_token = (
        auth_probe.require_fresh_access_token(
            token_file=selected_token_file
        )
    )

    assert access_token == "selected-role-token"