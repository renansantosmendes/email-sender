"""Settings of the email API, read from the environment or the .env file.

The variables are the ones auth_service uses for its tokens, so the API
accepts exactly the tokens that auth_service issues:

- AUTH_SERVICE_URL: base URL of auth_service.
- AUTH_JWT_ISSUER: issuer of the access tokens.
- AUTH_JWT_AUDIENCE: audience of the access tokens.
"""

import os
from dataclasses import dataclass

DEFAULT_AUTH_SERVICE_URL = "https://authservice-delta.vercel.app"
DEFAULT_ISSUER = "auth-service"
DEFAULT_AUDIENCE = "synapse-apps"


@dataclass(frozen=True)
class AuthSettings:
    """Values needed to verify the tokens of auth_service.

    Attributes
    ----------
    service_url : str
        Base URL of auth_service.
    issuer : str
        Expected ``iss`` claim of the access tokens.
    audience : str
        Expected ``aud`` claim of the access tokens.
    """

    service_url: str
    issuer: str
    audience: str


def load_auth_settings() -> AuthSettings:
    """Read the auth_service settings from the environment.

    Returns
    -------
    AuthSettings
        Settings, with the defaults of the deployed auth_service when a
        variable is not set.

    Example
    -------
    >>> load_auth_settings().issuer  # doctest: +SKIP
    'auth-service'
    """
    return AuthSettings(
        service_url=os.environ.get(
            "AUTH_SERVICE_URL",
            DEFAULT_AUTH_SERVICE_URL,
        ),
        issuer=os.environ.get("AUTH_JWT_ISSUER", DEFAULT_ISSUER),
        audience=os.environ.get("AUTH_JWT_AUDIENCE", DEFAULT_AUDIENCE),
    )
