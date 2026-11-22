from __future__ import annotations

import smtplib
from email.message import EmailMessage

from triage.ports.mailer import Mailer


class NullMailer(Mailer):
    """File-only escalation path. send() succeeds without delivering."""

    def send(self, to: str, subject: str, body: str) -> None:
        return None


class SmtpMailer(Mailer):
    def __init__(
        self, host: str, port: int, user: str, password: str, sender: str = ""
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender or user or "triage@localhost"

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)
