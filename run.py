"""Send the example email to the account owner.

The key and the sender come from the .env file (RESEND_API_KEY and
RESEND_FROM), so no secret is written in the code.
"""

from dotenv import load_dotenv

from send_email import send_email

load_dotenv()

email_id = send_email(
    recipient="renansantosmendes@gmail.com",
    subject="Hello World",
    text="Congrats on sending your first email!",
)
print(f"Email enviado (id {email_id}).")
