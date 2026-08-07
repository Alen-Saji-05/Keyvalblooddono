"""Recorded donations against a request."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utc_now_column

if TYPE_CHECKING:
    from .blood_request import BloodRequest
    from .donor import Donor
    from .user import User


class Donation(Base):
    """One donor giving a quantity of units towards one request.

    This table is the authority for fulfilment. ``blood_requests.units_fulfilled`` is
    recomputed as the sum over these rows, so a request can and normally does have
    several, each from a different donor.

    There is deliberately no unique constraint on ``(donor_id, request_id)``. A donor
    could legitimately give again to a long-running request after their cooldown has
    elapsed, and the eligibility rules already prevent the unsafe case.
    """

    __tablename__ = "donations"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    # RESTRICT, unlike most foreign keys here. A donation is a medical record. Removing a
    # donor must not silently delete the history of blood they gave, nor retroactively
    # change the fulfilment total of a request that was met.
    donor_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("donors.id", ondelete="RESTRICT", name="fk_donations_donor_id_donors"),
        nullable=False,
    )

    # CASCADE: a donation only has meaning relative to its request, so if the request is
    # removed the donation rows go with it.
    request_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey(
            "blood_requests.id", ondelete="CASCADE", name="fk_donations_request_id_blood_requests"
        ),
        nullable=False,
    )

    units_given: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    donation_date: Mapped[date] = mapped_column(sa.Date, nullable=False)

    # Who entered the record. Only an administrator can record a donation, and since
    # these rows drive every fulfilment and analytics figure it is worth knowing which
    # account wrote each one.
    recorded_by_user_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        sa.ForeignKey(
            "users.id", ondelete="SET NULL", name="fk_donations_recorded_by_user_id_users"
        ),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=utc_now_column()
    )

    donor: Mapped["Donor"] = relationship(back_populates="donations")
    request: Mapped["BloodRequest"] = relationship(back_populates="donations")
    recorded_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        sa.CheckConstraint("units_given > 0", name="units_given_positive"),
        # A guard against a data-entry slip becoming a fulfilled request. No single
        # whole blood donation is anywhere near this large.
        sa.CheckConstraint("units_given <= 10", name="units_given_plausible"),
        sa.Index("ix_donations_request_id", "request_id"),
        sa.Index("ix_donations_donor_id", "donor_id"),
        sa.Index("ix_donations_donation_date", "donation_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Donation id={self.id} donor={self.donor_id} "
            f"request={self.request_id} units={self.units_given}>"
        )
