"""Broadcast notifications sent to donors."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utc_now_column
from .enums import NotificationChannel
from .types import pg_enum

if TYPE_CHECKING:
    from .blood_request import BloodRequest
    from .donor import Donor


class Notification(Base):
    """One donor being told about one request.

    These rows are the source of truth for outreach, independently of whether any
    external message was actually delivered. That separation is what makes the donor
    response rate a well defined figure even when the configured delivery driver is the
    console: the denominator is the number of rows, and the numerator is the number with
    ``responded`` set.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    donor_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("donors.id", ondelete="CASCADE", name="fk_notifications_donor_id_donors"),
        nullable=False,
    )
    request_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey(
            "blood_requests.id",
            ondelete="CASCADE",
            name="fk_notifications_request_id_blood_requests",
        ),
        nullable=False,
    )

    sent_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=utc_now_column()
    )

    responded: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    response_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Which driver handled delivery, recorded per row rather than read from
    # configuration when the record is displayed, so that switching drivers later does
    # not rewrite how past broadcasts appear to have been sent.
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel"),
        nullable=False,
        server_default=NotificationChannel.CONSOLE.value,
    )
    # Set when the driver raised an error. The notification row still exists and still
    # counts as outreach that was attempted, which is why a delivery failure does not
    # abort the whole broadcast.
    delivery_error: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    donor: Mapped["Donor"] = relationship(back_populates="notifications")
    request: Mapped["BloodRequest"] = relationship(back_populates="notifications")

    __table_args__ = (
        # Re-broadcasting a request that is still short of units is a normal thing to do.
        # Without this constraint the second broadcast would create a second row for the
        # same donor, inflating the denominator of the response rate and sending a
        # duplicate message. The broadcast service therefore skips donors already
        # notified about this request.
        sa.UniqueConstraint("donor_id", "request_id", name="uq_notifications_donor_id_request_id"),
        # A response has a time, and a non-response does not have one. Keeping the two
        # columns in step at the database level means the response rate cannot be
        # computed from one column while the timestamps say something else.
        sa.CheckConstraint(
            "(responded = true AND response_at IS NOT NULL) "
            "OR (responded = false AND response_at IS NULL)",
            name="response_at_matches_responded",
        ),
        sa.Index("ix_notifications_donor_id_sent_at", "donor_id", "sent_at"),
        sa.Index("ix_notifications_request_id", "request_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} donor={self.donor_id} "
            f"request={self.request_id} responded={self.responded}>"
        )
