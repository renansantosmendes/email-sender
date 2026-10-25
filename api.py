"""HTTP API that sends emails for the users of auth_service.

Every request to ``/me`` and ``/emails`` must carry the access token that
auth_service issues at login, in the ``Authorization: Bearer`` header. The
token is verified locally against the public keys of auth_service.

Run it from the project folder:

    uv run uvicorn api:app --reload
"""

import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

import resend
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from auth import (
    AuthenticatedUser,
    AuthServiceUnavailableError,
    InvalidTokenError,
    TokenVerifier,
    jwks_url,
)
from config import load_auth_settings
from send_email import send_email

load_dotenv()

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="AuthServiceToken",
    description=(
        "Access token returned by `POST /api/v1/auth/login` of auth_service. "
        "Paste only the token, without the `Bearer` prefix."
    ),
)

app = FastAPI(
    title="Email Sender API",
    version="1.0.0",
    description=(
        "Sends emails with Resend for the users authenticated by auth_service."
    ),
)


class EmailRequest(BaseModel):
    """Body of `POST /emails`.

    Attributes
    ----------
    to : EmailStr
        Address the email is sent to.
    subject : str
        Subject line, from 1 to 200 characters.
    text : str
        Plain-text body, from 1 to 10000 characters.
    """

    to: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)


class EmailResponse(BaseModel):
    """Reply of `POST /emails`.

    Attributes
    ----------
    id : str
        Identifier that Resend assigned to the email.
    """

    id: str


class UserResponse(BaseModel):
    """User identified by the access token, returned by `GET /me`.

    Attributes
    ----------
    user_id : str
        Identifier of the user in auth_service.
    email : str
        Email address of the user.
    name : str
        Full name of the user.
    """

    user_id: str
    email: str
    name: str


@lru_cache
def get_token_verifier() -> TokenVerifier:
    """Provide the token verifier, created once per process.

    Returns
    -------
    TokenVerifier
        Verifier configured with the settings of auth_service.
    """
    settings = load_auth_settings()
    return TokenVerifier(
        jwks_url(settings.service_url),
        settings.issuer,
        settings.audience,
    )


def get_send_email() -> Callable[..., str]:
    """Provide the function that sends an email through Resend.

    Returns
    -------
    Callable[..., str]
        The ``send_email`` function, which returns the Resend email id.
    """
    return send_email


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    """Identify the user of the request from its access token.

    Parameters
    ----------
    credentials : HTTPAuthorizationCredentials | None
        Bearer credentials of the request, when present.
    verifier : TokenVerifier
        Verifier of the access tokens.

    Returns
    -------
    AuthenticatedUser
        The user the token was issued to.

    Raises
    ------
    HTTPException
        401 when the token is missing or invalid, and 503 when auth_service
        cannot be reached to verify it.
    """
    if credentials is None:
        raise _unauthorized("Missing access token.")
    try:
        return verifier.verify(credentials.credentials)
    except InvalidTokenError as error:
        raise _unauthorized(str(error)) from error
    except AuthServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from error


def _unauthorized(detail: str) -> HTTPException:
    """Build the error returned for a request without a valid token.

    Parameters
    ----------
    detail : str
        Short description of the problem.

    Returns
    -------
    HTTPException
        Error with status 401 and the Bearer challenge header.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/health", summary="Health check")
def health() -> dict[str, str]:
    """Report that the API is running.

    Returns
    -------
    dict[str, str]
        ``{"status": "ok"}``.
    """
    return {"status": "ok"}


@app.get("/me", response_model=UserResponse, summary="Current user")
def read_current_user(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> UserResponse:
    """Return the user identified by the access token.

    Parameters
    ----------
    user : AuthenticatedUser
        User of the request.

    Returns
    -------
    UserResponse
        Identifier, email and name of the user.
    """
    return UserResponse(user_id=user.user_id, email=user.email, name=user.name)


@app.post(
    "/emails",
    response_model=EmailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send an email",
    responses={
        401: {"description": "Missing or invalid access token."},
        502: {"description": "Resend rejected the email."},
        503: {"description": "Email service or authentication unavailable."},
    },
)
def create_email(
    request: EmailRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    sender: Annotated[Callable[..., str], Depends(get_send_email)],
) -> EmailResponse:
    """Send an email to the address of the request.

    The sender address is the RESEND_FROM of the server. The request is
    logged with the user identifier and the Resend email id, never with the
    message text.

    Parameters
    ----------
    request : EmailRequest
        Recipient, subject and body of the email.
    user : AuthenticatedUser
        User who asks for the email.
    sender : Callable[..., str]
        Function that sends the email and returns its id.

    Returns
    -------
    EmailResponse
        Identifier that Resend assigned to the email.

    Raises
    ------
    HTTPException
        503 when the email service is not configured, and 502 when Resend
        rejects the email.
    """
    try:
        email_id = sender(
            recipient=str(request.to),
            subject=request.subject,
            text=request.text,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured.",
        ) from error
    except resend.exceptions.ResendError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resend rejected the email.",
        ) from error
    logger.info("Email %s sent for user %s", email_id, user.user_id)
    return EmailResponse(id=email_id)
