"""Concrete notification drivers."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

from ..models.enums import NotificationChannel
from .base import Notifier, NotificationMessage

logger = logging.getLogger("app.notifications")


class ConsoleNotifier(Notifier):
    """Writes the message to the application log.

    The default, and the only driver that works with no external configuration. It exists
    so the broadcast feature is fully exercisable - the notification rows, the response
    rate, the donor inbox - without an SMTP server, and so that what a donor would receive
    can be read during development.
    """

    channel = NotificationChannel.CONSOLE

    def deliver(self, message: NotificationMessage) -> None:
        logger.info(
            "Notification to %s <%s / %s>: %s\n%s",
            message.recipient_name,
            message.recipient_email or "no email",
            message.recipient_phone,
            message.subject,
            message.body,
        )


class NullNotifier(Notifier):
    """Discards messages. Used by the test configuration.

    Distinct from the console driver so that the test suite is not measured against log
    output, and so a test asserting on delivery failures is not competing with hundreds of
    lines of message text.
    """

    channel = NotificationChannel.CONSOLE

    def deliver(self, message: NotificationMessage) -> None:
        return None


class EmailNotifier(Notifier):
    """Sends over SMTP.

    Enabled by setting NOTIFIER_DRIVER=smtp along with the SMTP_* settings. A donor with
    no email address on file raises, and the broadcast records that against their
    notification rather than failing the whole operation.
    """

    channel = NotificationChannel.EMAIL

    def deliver(self, message: NotificationMessage) -> None:
        if not message.recipient_email:
            raise ValueError("Donor has no email address on file.")

        config = current_app.config
        host = config.get("SMTP_HOST")
        if not host:
            raise RuntimeError("SMTP_HOST is not configured.")

        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = config["SMTP_FROM"]
        email["To"] = message.recipient_email
        email.set_content(message.body)

        # A timeout is set explicitly. Without one, smtplib blocks on the operating
        # system default, which can be minutes, and a broadcast to a large donor list
        # would hold the request open long past any sensible limit.
        with smtplib.SMTP(host, config["SMTP_PORT"], timeout=10) as server:
            if config.get("SMTP_USE_TLS"):
                server.starttls()
            if config.get("SMTP_USERNAME"):
                server.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            server.send_message(email)


_DRIVERS = {
    "console": ConsoleNotifier,
    "null": NullNotifier,
    "smtp": EmailNotifier,
    "email": EmailNotifier,
}


def get_notifier() -> Notifier:
    """Build the configured driver.

    An unrecognised name falls back to the console driver with a warning rather than
    raising. A typo in an environment variable should not take down the ability to
    broadcast, which is the one thing this system exists to do; losing external delivery
    while keeping the notification records is the milder failure.
    """

    name = (current_app.config.get("NOTIFIER_DRIVER") or "console").strip().lower()
    driver = _DRIVERS.get(name)
    if driver is None:
        logger.warning("Unknown NOTIFIER_DRIVER %r, falling back to console.", name)
        driver = ConsoleNotifier
    return driver()
