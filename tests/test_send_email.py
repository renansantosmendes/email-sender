"""Tests of the Resend sender, with the Resend call replaced."""

from typing import Any

import pytest

from send_email import DEFAULT_SENDER, build_payload, send_email


def test_payload_follows_the_resend_format() -> None:
    payload = build_payload("de@x.com", "para@y.com", "Oi", "Texto")
    assert payload == {
        "from": "de@x.com",
        "to": ["para@y.com"],
        "subject": "Oi",
        "text": "Texto",
    }


@pytest.fixture
def captured_payloads(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the Resend call and record the payloads it receives.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture that replaces the Resend call for the test.

    Returns
    -------
    list[dict[str, Any]]
        Payloads sent to Resend during the test.
    """
    payloads: list[dict[str, Any]] = []

    def fake_send(params: dict[str, Any]) -> dict[str, str]:
        payloads.append(params)
        return {"id": "re_test"}

    monkeypatch.setattr("send_email.resend.Emails.send", fake_send)
    return payloads


def test_send_email_returns_the_resend_id(
    monkeypatch: pytest.MonkeyPatch,
    captured_payloads: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    monkeypatch.setenv("RESEND_FROM", "noreply@x.com")
    email_id = send_email("para@y.com", "Oi", "Texto")
    assert email_id == "re_test"
    assert captured_payloads[0]["from"] == "noreply@x.com"


def test_sender_falls_back_to_the_resend_test_address(
    monkeypatch: pytest.MonkeyPatch,
    captured_payloads: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_key")
    monkeypatch.delenv("RESEND_FROM", raising=False)
    send_email("para@y.com", "Oi", "Texto")
    assert captured_payloads[0]["from"] == DEFAULT_SENDER


def test_missing_api_key_stops_before_calling_resend(
    monkeypatch: pytest.MonkeyPatch,
    captured_payloads: list[dict[str, Any]],
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        send_email("para@y.com", "Oi", "Texto")
    assert captured_payloads == []
