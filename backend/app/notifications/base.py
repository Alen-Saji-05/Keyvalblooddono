"""The notification delivery interface.

Delivery is separated from the record of it. A broadcast writes one ``notifications`` row
per selected donor, and that row is the source of truth: it is what the donor's inbox
reads and what the response-rate analytic counts. Whether an external message also went
out is a second, fallible thing.

That separation buys two properties. The response rate is well defined even when no mail
server is configured, and a delivery failure marks one notification rather than aborting a
broadcast to two hundred people.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import BloodRequest, Donor
from ..models.enums import NotificationChannel


@dataclass(frozen=True)
class NotificationMessage:
    """The rendered content of one notification.

    Built once per recipient by the notifier base class so that every driver sends the
    same words. A driver that composed its own text would drift from the others, and the
    console output would stop being a faithful preview of what a donor actually receives.
    """

    subject: str
    body: str
    recipient_name: str
    recipient_email: str | None
    recipient_phone: str


class Notifier(ABC):
    """A delivery driver."""

    channel: NotificationChannel

    def build_message(self, donor: Donor, request: BloodRequest) -> NotificationMessage:
        """Compose the message for one donor.

        The units still outstanding are stated rather than the units originally required,
        because a donor deciding whether to travel to a hospital needs to know what is
        still needed, not what was needed before four other people turned up.
        """

        outstanding = request.units_outstanding
        subject = f"{request.blood_group.value} blood needed at {request.hospital}"
        body = (
            f"Hello {donor.name},\n\n"
            f"A patient at {request.hospital} in {request.place} needs "
            f"{request.blood_group.value} blood.\n\n"
            f"Units still needed: {outstanding} of {request.units_required}\n"
            f"Needed by: {request.needed_by_date.isoformat()}\n"
            f"Contact: {request.contact_phone}\n\n"
            "If you are able to help, please respond through the donor portal or call the "
            "number above.\n\n"
            "If you are unwell, have donated recently, or cannot travel, you do not need to "
            "do anything.\n"
        )
        return NotificationMessage(
            subject=subject,
            body=body,
            recipient_name=donor.name,
            recipient_email=donor.email,
            recipient_phone=donor.phone,
        )

    @abstractmethod
    def deliver(self, message: NotificationMessage) -> None:
        """Send one message, raising on failure.

        Raising rather than returning a boolean is deliberate: the caller records the
        exception text in ``notifications.delivery_error``, and a boolean would discard
        the one piece of information that makes a failure diagnosable.
        """

    def send(self, donor: Donor, request: BloodRequest) -> None:
        self.deliver(self.build_message(donor, request))
