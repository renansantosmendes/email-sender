"""Send one email to a user through the Resend API.

The API key and the sender address are read from the environment (or from a
local .env file): RESEND_API_KEY and RESEND_FROM. Run it from the command
line with the recipient, the subject and the message:

    uv run python send_email.py user@example.com "Assunto" "Olá!"
"""

import argparse
import os
import sys
from typing import Any

import resend
from dotenv import load_dotenv

DEFAULT_SENDER = "onboarding@resend.dev"


def build_payload(
    sender: str,
    recipient: str,
    subject: str,
    text: str,
) -> dict[str, Any]:
    """Build the parameters expected by ``resend.Emails.send``.

    Parameters
    ----------
    sender : str
        Address the email is sent from. Must belong to a domain verified in
        Resend, or be the Resend test sender.
    recipient : str
        Address the email is sent to.
    subject : str
        Subject line.
    text : str
        Plain-text body.

    Returns
    -------
    dict[str, Any]
        Parameters for ``resend.Emails.send``.

    Example
    -------
    >>> build_payload("a@x.com", "b@y.com", "Oi", "Texto")["to"]
    ['b@y.com']
    """
    return {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "text": text,
    }


def send_email(
    recipient: str,
    subject: str,
    text: str,
    sender: str | None = None,
) -> str:
    """Send an email and return the id Resend assigned to it.

    Parameters
    ----------
    recipient : str
        Address the email is sent to.
    subject : str
        Subject line.
    text : str
        Plain-text body.
    sender : str | None
        Sender address. When omitted, RESEND_FROM is used, and if that is not
        set either, the Resend test sender.

    Returns
    -------
    str
        Identifier of the email in Resend.

    Raises
    ------
    RuntimeError
        When RESEND_API_KEY is not configured.

    Example
    -------
    >>> send_email("user@example.com", "Bem-vindo", "Olá!")  # doctest: +SKIP
    're_123abc'
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not set. Put it in the environment or in a .env file."
        )
    resend.api_key = api_key
    from_address = sender or os.environ.get("RESEND_FROM") or DEFAULT_SENDER
    response = resend.Emails.send(build_payload(from_address, recipient, subject, text))
    return response["id"]


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Read the command-line arguments.

    Parameters
    ----------
    argv : list[str]
        Arguments without the program name.

    Returns
    -------
    argparse.Namespace
        Parsed recipient, subject and message.

    Example
    -------
    >>> parse_arguments(["a@x.com", "Oi", "Texto"]).recipient
    'a@x.com'
    """
    parser = argparse.ArgumentParser(description="Send an email with Resend.")
    parser.add_argument("recipient", help="Address the email is sent to.")
    parser.add_argument("subject", help="Subject line.")
    parser.add_argument("text", help="Plain-text body.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Send the email described by the command line.

    Parameters
    ----------
    argv : list[str]
        Arguments without the program name.

    Returns
    -------
    int
        Exit status: 0 when the email was accepted by Resend, 1 otherwise.
    """
    load_dotenv()
    arguments = parse_arguments(argv)
    try:
        email_id = send_email(arguments.recipient, arguments.subject, arguments.text)
    except (RuntimeError, resend.exceptions.ResendError) as error:
        print(f"Erro ao enviar: {error}", file=sys.stderr)
        return 1
    print(f"Email enviado para {arguments.recipient} (id {email_id}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
