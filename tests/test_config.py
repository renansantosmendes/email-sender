"""Tests of the auth_service settings read from the environment."""

import pytest

from config import (
    DEFAULT_AUDIENCE,
    DEFAULT_AUTH_SERVICE_URL,
    DEFAULT_ISSUER,
    load_auth_settings,
)


def test_settings_default_to_the_deployed_auth_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("AUTH_SERVICE_URL", "AUTH_JWT_ISSUER", "AUTH_JWT_AUDIENCE"):
        monkeypatch.delenv(name, raising=False)
    settings = load_auth_settings()
    assert settings.service_url == DEFAULT_AUTH_SERVICE_URL
    assert settings.issuer == DEFAULT_ISSUER
    assert settings.audience == DEFAULT_AUDIENCE


def test_settings_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_SERVICE_URL", "https://auth.example.com")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "issuer-x")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "audience-y")
    settings = load_auth_settings()
    assert settings.service_url == "https://auth.example.com"
    assert settings.issuer == "issuer-x"
    assert settings.audience == "audience-y"
