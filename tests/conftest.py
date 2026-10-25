"""Shared fixtures: an RSA key pair, tokens signed with it, and a key client.

The tests never reach auth_service: the public key is handed to the verifier
through a fake key client that behaves like ``PyJWKClient``.
"""

import time
import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "auth-service"
AUDIENCE = "synapse-apps"
KEY_ID = "test-key-1"


@pytest.fixture(scope="session")
def private_key() -> rsa.RSAPrivateKey:
    """Create the RSA key that signs the test tokens.

    Returns
    -------
    rsa.RSAPrivateKey
        Private key shared by the tests of the session.
    """
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def make_token(
    private_key: rsa.RSAPrivateKey,
) -> Callable[..., str]:
    """Provide a function that signs access tokens like auth_service does.

    Parameters
    ----------
    private_key : rsa.RSAPrivateKey
        Key that signs the tokens.

    Returns
    -------
    Callable[..., str]
        Function that returns a signed token. Its keyword arguments replace
        any claim, and ``None`` removes the claim.
    """

    def build(**overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(uuid.uuid4()),
            "sid": str(uuid.uuid4()),
            "email": "ana@example.com",
            "name": "Ana Souza",
            "typ": "access",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 900,
        }
        for name, value in overrides.items():
            if value is None:
                claims.pop(name, None)
            else:
                claims[name] = value
        return jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers={"kid": KEY_ID},
        )

    return build


class FakeKeyClient:
    """Stand-in for ``PyJWKClient`` that returns the test public key.

    Parameters
    ----------
    public_key : Any
        Public key returned for every token.
    """

    def __init__(self, public_key: Any) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        """Return the signing key of a token.

        Parameters
        ----------
        token : str
            Token whose key is requested.

        Returns
        -------
        SimpleNamespace
            Object with a ``key`` attribute holding the public key.
        """
        return SimpleNamespace(key=self._public_key)


@pytest.fixture
def key_client(private_key: rsa.RSAPrivateKey) -> FakeKeyClient:
    """Provide a key client that verifies the test tokens.

    Parameters
    ----------
    private_key : rsa.RSAPrivateKey
        Key whose public part is served.

    Returns
    -------
    FakeKeyClient
        Key client for the verifier.
    """
    return FakeKeyClient(private_key.public_key())
