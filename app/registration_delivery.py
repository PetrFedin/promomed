"""Verification-code delivery for participant self-registration.

Production requires configured SMTP with TLS. Secrets and codes are never logged.
Demo mode may bypass SMTP and return the code to deterministic browser/CI tests.
"""
import os
import smtplib
from email.message import EmailMessage


def configured():
    return bool(
        os.environ.get("PROMOMED_REGISTRATION_SMTP_HOST", "").strip()
        and os.environ.get("PROMOMED_REGISTRATION_FROM_EMAIL", "").strip()
    )


def send_verification(email, code, request_id):
    host = os.environ.get("PROMOMED_REGISTRATION_SMTP_HOST", "").strip()
    sender = os.environ.get("PROMOMED_REGISTRATION_FROM_EMAIL", "").strip()
    if not host or not sender:
        raise RuntimeError("registration_delivery_unconfigured")
    port = int(os.environ.get("PROMOMED_REGISTRATION_SMTP_PORT", "587"))
    user = os.environ.get("PROMOMED_REGISTRATION_SMTP_USER", "")
    password = os.environ.get("PROMOMED_REGISTRATION_SMTP_PASSWORD", "")
    if port < 1 or port > 65535:
        raise RuntimeError("registration_delivery_invalid_port")

    message = EmailMessage()
    message["Subject"] = "Код подтверждения СОСТОЯНИЕ"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "Код подтверждения: " + code + "\n\n"
        "Код действует ограниченное время. Если вы не запрашивали регистрацию, "
        "проигнорируйте это письмо.\n"
        "Request: " + request_id
    )

    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)
