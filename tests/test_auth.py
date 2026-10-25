"""Tests of the verification of auth_service access tokens."""

import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from auth import (
    AuthenticatedUser,
    AuthServiceUnavailableError,
    InvalidTokenError,
    TokenVerifier,
    jwks_url,
)
from tests.conftest import AUDIENCE, ISSUER


@pytest.fixture
def verifier(key_client: Any) -> TokenVerifier:
    """Provide a verifier wired to the test key client.

    Parameters
    ----------
    key_client : Any
        Fake key client that serves the test public key.

    Returns
    -------
    TokenVerifier
        Verifier for the test issuer and audience.
    """
    return TokenVerifier(
        "https://auth.example.com/.well-known/jwks.json",
        ISSUER,
        AUDIENCE,
        key_client=key_client,
    )


def test_valid_token_identifies_its_user(
    verifier: TokenVerifier,
    make_token: Callable[..., str],
) -> None:
    token = make_token(sub="user-1", email="ana@example.com", name="Ana")
    user = verifier.verify(token)
    assert user == AuthenticatedUser(
        user_id="user-1",
        email="ana@example.com",
        name="Ana",
    )


def test_token_without_profile_claims_still_identifies_the_user(
    verifier: TokenVerifier,
    make_token: Callable[..., str],
) -> None:
    user = verifier.verify(make_token(email=None, name=None))
    assert user.email == ""
    assert user.name == ""


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-app"},
        {"iss": "someone-else"},
        {"typ": "refresh"},
        {"exp": int(time.time()) - 60},
        {"sid": None},
    ],
    ids=["audience", "issuer", "type", "expired", "missing-session"],
)
def test_token_failing_a_claim_check_is_rejected(
    verifier: TokenVerifier,
    make_token: Callable[..., str],
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(make_token(**overrides))


def test_malformed_token_is_rejected(verifier: TokenVerifier) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify("not-a-jwt")


def test_token_with_unknown_key_is_rejected(verifier: TokenVerifier) -> None:
    class UnknownKeyClient:
        def get_signing_key_from_jwt(self, token: str) -> None:
            raise PyJWKClientError("Unable to find a signing key")

    unknown = TokenVerifier(
        "https://auth.example.com/.well-known/jwks.json",
        ISSUER,
        AUDIENCE,
        key_client=UnknownKeyClient(),
    )
    with pytest.raises(InvalidTokenError):
        unknown.verify("a.b.c")


def test_unreachable_auth_service_is_reported_as_unavailable() -> None:
    class DownKeyClient:
        def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
            raise PyJWKClientConnectionError("connection refused")

    down = TokenVerifier(
        "https://auth.example.com/.well-known/jwks.json",
        ISSUER,
        AUDIENCE,
        key_client=DownKeyClient(),
    )
    with pytest.raises(AuthServiceUnavailableError):
        down.verify("a.b.c")


def test_jwks_url_joins_the_base_url_once() -> None:
    assert jwks_url("https://auth.example.com/") == (
        "https://auth.example.com/.well-known/jwks.json"
    )
    assert jwks_url("https://auth.example.com") == (
        "https://auth.example.com/.well-known/jwks.json"
    )
