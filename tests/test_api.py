"""Tests of the HTTP API, with the token checks and the sender replaced."""

from collections.abc import Callable
from typing import Any

import pytest
import resend
from fastapi.testclient import TestClient

from api import app, get_send_email, get_token_verifier
from auth import AuthServiceUnavailableError, TokenVerifier
from tests.conftest import AUDIENCE, ISSUER


class RecordingSender:
    """Sender that records its calls and returns a fixed email id.

    Parameters
    ----------
    result : str
        Identifier returned for every email.
    error : Exception | None
        Exception raised instead of sending, when set.
    """

    def __init__(
        self,
        result: str = "re_123",
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, str]] = []

    def __call__(self, **kwargs: str) -> str:
        """Record the email and return its id.

        Parameters
        ----------
        **kwargs : str
            Recipient, subject and text of the email.

        Returns
        -------
        str
            The fixed email id.

        Raises
        ------
        Exception
            The configured error, when one was given.
        """
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def sender() -> RecordingSender:
    """Provide a sender that records the emails of a test.

    Returns
    -------
    RecordingSender
        Fresh recording sender.
    """
    return RecordingSender()


@pytest.fixture
def client(
    key_client: Any,
    sender: RecordingSender,
) -> Any:
    """Provide an API client that verifies test tokens and records emails.

    Parameters
    ----------
    key_client : Any
        Fake key client that serves the test public key.
    sender : RecordingSender
        Sender that replaces Resend.

    Returns
    -------
    Any
        Test client of the application, with its overrides removed afterwards.
    """
    verifier = TokenVerifier(
        "https://auth.example.com/.well-known/jwks.json",
        ISSUER,
        AUDIENCE,
        key_client=key_client,
    )
    app.dependency_overrides[get_token_verifier] = lambda: verifier
    app.dependency_overrides[get_send_email] = lambda: sender
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header(token: str) -> dict[str, str]:
    """Build the Authorization header of a request.

    Parameters
    ----------
    token : str
        Access token, without the ``Bearer`` prefix.

    Returns
    -------
    dict[str, str]
        Header with the bearer token.
    """
    return {"Authorization": "Bearer " + token}


VALID_EMAIL = {
    "to": "destino@example.com",
    "subject": "Assunto",
    "text": "Mensagem",
}


def test_health_needs_no_token(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_returns_the_user_of_the_token(
    client: TestClient,
    make_token: Callable[..., str],
) -> None:
    token = make_token(sub="user-7", email="ana@example.com", name="Ana")
    response = client.get("/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-7",
        "email": "ana@example.com",
        "name": "Ana",
    }


def test_request_without_token_is_rejected(
    client: TestClient,
    sender: RecordingSender,
) -> None:
    response = client.post("/emails", json=VALID_EMAIL)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert sender.calls == []


def test_request_with_invalid_token_is_rejected(
    client: TestClient,
    sender: RecordingSender,
    make_token: Callable[..., str],
) -> None:
    token = make_token(aud="another-app")
    response = client.post(
        "/emails",
        json=VALID_EMAIL,
        headers=auth_header(token),
    )
    assert response.status_code == 401
    assert sender.calls == []


def test_authenticated_user_sends_an_email(
    client: TestClient,
    sender: RecordingSender,
    make_token: Callable[..., str],
) -> None:
    response = client.post(
        "/emails",
        json=VALID_EMAIL,
        headers=auth_header(make_token()),
    )
    assert response.status_code == 202
    assert response.json() == {"id": "re_123"}
    assert sender.calls == [
        {
            "recipient": "destino@example.com",
            "subject": "Assunto",
            "text": "Mensagem",
        }
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"to": "nao-e-email", "subject": "A", "text": "B"},
        {"to": "destino@example.com", "subject": "", "text": "B"},
        {"to": "destino@example.com", "subject": "A", "text": ""},
        {"to": "destino@example.com", "subject": "x" * 201, "text": "B"},
    ],
    ids=["address", "empty-subject", "empty-text", "long-subject"],
)
def test_invalid_email_is_refused_before_sending(
    client: TestClient,
    sender: RecordingSender,
    make_token: Callable[..., str],
    body: dict[str, str],
) -> None:
    response = client.post(
        "/emails",
        json=body,
        headers=auth_header(make_token()),
    )
    assert response.status_code == 422
    assert sender.calls == []


def test_missing_resend_key_is_reported_as_unavailable(
    client: TestClient,
    make_token: Callable[..., str],
) -> None:
    app.dependency_overrides[get_send_email] = lambda: RecordingSender(
        error=RuntimeError("RESEND_API_KEY is not set."),
    )
    response = client.post(
        "/emails",
        json=VALID_EMAIL,
        headers=auth_header(make_token()),
    )
    assert response.status_code == 503


def test_resend_rejection_is_reported_as_bad_gateway(
    client: TestClient,
    make_token: Callable[..., str],
) -> None:
    error = resend.exceptions.ResendError(
        code=422,
        error_type="validation_error",
        message="Invalid sender",
        suggested_action="Use a verified domain",
    )
    app.dependency_overrides[get_send_email] = lambda: RecordingSender(
        error=error,
    )
    response = client.post(
        "/emails",
        json=VALID_EMAIL,
        headers=auth_header(make_token()),
    )
    assert response.status_code == 502


def test_auth_service_outage_is_reported_as_unavailable(
    client: TestClient,
    make_token: Callable[..., str],
) -> None:
    class DownVerifier:
        def verify(self, token: str) -> None:
            raise AuthServiceUnavailableError("down")

    app.dependency_overrides[get_token_verifier] = lambda: DownVerifier()
    response = client.post(
        "/emails",
        json=VALID_EMAIL,
        headers=auth_header(make_token()),
    )
    assert response.status_code == 503
