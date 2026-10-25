"""Verify the access tokens issued by auth_service.

Access tokens are RS256 JSON Web Tokens. Their public keys are published by
auth_service at ``/.well-known/jwks.json`` and cached by PyJWT, so each
request is verified locally, without calling auth_service again.
"""

from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWTError

ACCESS_TOKEN_TYPE = "access"
SIGNING_ALGORITHM = "RS256"
REQUIRED_CLAIMS = ["sub", "sid", "exp", "iat", "iss", "aud"]
JWKS_PATH = "/.well-known/jwks.json"


class InvalidTokenError(Exception):
    """Raised when an access token is missing, malformed or not valid."""


class AuthServiceUnavailableError(Exception):
    """Raised when the public keys of auth_service cannot be fetched."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """User identified by a valid access token.

    Attributes
    ----------
    user_id : str
        Identifier of the user in auth_service (the ``sub`` claim).
    email : str
        Email address of the user.
    name : str
        Full name of the user.
    """

    user_id: str
    email: str
    name: str


def jwks_url(base_url: str) -> str:
    """Build the URL of the public keys of an auth_service deployment.

    Parameters
    ----------
    base_url : str
        Base URL of auth_service, for example ``https://auth.example.com``.

    Returns
    -------
    str
        URL of the JSON Web Key Set.

    Example
    -------
    >>> jwks_url("https://auth.example.com/")
    'https://auth.example.com/.well-known/jwks.json'
    """
    return base_url.rstrip("/") + JWKS_PATH


class TokenVerifier:
    """Check the signature and the claims of access tokens from auth_service.

    Parameters
    ----------
    jwks_address : str
        URL of the JSON Web Key Set of auth_service.
    issuer : str
        Expected ``iss`` claim, the ``AUTH_JWT_ISSUER`` of auth_service.
    audience : str
        Expected ``aud`` claim, the ``AUTH_JWT_AUDIENCE`` of auth_service.
    key_client : PyJWKClient | None
        Client that fetches the signing keys. When omitted, a client that
        caches the keys is created for ``jwks_address``.

    Example
    -------
    >>> verifier = TokenVerifier(
    ...     "https://auth.example.com/.well-known/jwks.json",
    ...     "auth-service",
    ...     "synapse-apps",
    ... )
    >>> verifier.verify("token-from-login")  # doctest: +SKIP
    AuthenticatedUser(user_id='...', email='...', name='...')
    """

    def __init__(
        self,
        jwks_address: str,
        issuer: str,
        audience: str,
        key_client: PyJWKClient | None = None,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_client = key_client or PyJWKClient(
            jwks_address,
            cache_keys=True,
        )

    def verify(self, token: str) -> AuthenticatedUser:
        """Validate an access token and return the user it identifies.

        Parameters
        ----------
        token : str
            Access token, without the ``Bearer`` prefix.

        Returns
        -------
        AuthenticatedUser
            The user the token was issued to.

        Raises
        ------
        InvalidTokenError
            When the token is malformed, expired, has an unknown key or a
            wrong issuer, audience or type.
        AuthServiceUnavailableError
            When the public keys of auth_service cannot be fetched.
        """
        signing_key = self._signing_key(token)
        claims = self._decode(token, signing_key)
        if claims.get("typ") != ACCESS_TOKEN_TYPE:
            raise InvalidTokenError("The token is not an access token.")
        return AuthenticatedUser(
            user_id=str(claims["sub"]),
            email=str(claims.get("email", "")),
            name=str(claims.get("name", "")),
        )

    def _signing_key(self, token: str) -> Any:
        """Find the public key that signed the token.

        Parameters
        ----------
        token : str
            Access token to inspect.

        Returns
        -------
        Any
            The key object that PyJWT uses to verify the signature.

        Raises
        ------
        InvalidTokenError
            When the token has no known signing key.
        AuthServiceUnavailableError
            When the keys cannot be fetched.
        """
        try:
            return self._key_client.get_signing_key_from_jwt(token).key
        except PyJWKClientConnectionError as error:
            raise AuthServiceUnavailableError(
                "The keys of auth_service cannot be fetched."
            ) from error
        except PyJWTError as error:
            raise InvalidTokenError("Unknown signing key.") from error

    def _decode(self, token: str, signing_key: Any) -> dict[str, Any]:
        """Check the signature, the expiration and the claims of a token.

        Parameters
        ----------
        token : str
            Access token to decode.
        signing_key : Any
            Public key that verifies the signature.

        Returns
        -------
        dict[str, Any]
            Claims of the token.

        Raises
        ------
        InvalidTokenError
            When the token fails any check.
        """
        try:
            return jwt.decode(
                token,
                signing_key,
                algorithms=[SIGNING_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": REQUIRED_CLAIMS},
            )
        except PyJWTError as error:
            raise InvalidTokenError("Invalid access token.") from error
