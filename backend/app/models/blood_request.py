"""Blood requests raised by patients or by an administrator on their behalf."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import BloodGroup, RequestStatus
from .types import pg_enum

if TYPE_CHECKING:
    from .donation import Donation
    from .notification import Notification
    from .user import User


class BloodRequest(Base, TimestampMixin):
    """A need for a quantity of blood of a particular group, by a particular date.

    A request is rarely satisfied by one person. One donor gives roughly one unit, so a
    request for four units needs four donors, and the request has to remain actionable
    while it is partly met. That is why fulfilment is a running total and a three-state
    status rather than a boolean.
    """

    __tablename__ = "blood_requests"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    # Nullable and SET NULL on delete: an administrator can file a request on behalf of
    # someone with no account, and removing a user account later must not erase the
    # record that the request happened. Patient scoping keys off this column rather than
    # matching on the hospital name, because two people typing the same hospital
    # differently would otherwise see each other's requests.
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        sa.ForeignKey(
            "users.id", ondelete="SET NULL", name="fk_blood_requests_created_by_user_id_users"
        ),
        nullable=True,
    )

    patient_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    blood_group: Mapped[BloodGroup] = mapped_column(
        pg_enum(BloodGroup, "blood_group"), nullable=False
    )
    hospital: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    place: Mapped[str] = mapped_column(sa.String(120), nullable=False)

    # A request with no way to reach the requester is not actionable. This is not in the
    # starting schema but a donor who wants to help has to be able to call somebody.
    contact_phone: Mapped[str] = mapped_column(sa.String(20), nullable=False)

    units_required: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # A denormalised running total, recomputed from the donations table inside the same
    # transaction as every insert. It is a cache for reads and filters, never the
    # authority: services.fulfilment recalculates it with SUM rather than incrementing
    # it, so a mistaken value cannot compound.
    units_fulfilled: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )

    needed_by_date: Mapped[date] = mapped_column(sa.Date, nullable=False)

    status: Mapped[RequestStatus] = mapped_column(
        pg_enum(RequestStatus, "request_status"),
        nullable=False,
        server_default=RequestStatus.OPEN.value,
    )

    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    created_by: Mapped[Optional["User"]] = relationship(back_populates="requests")
    donations: Mapped[List["Donation"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        sa.CheckConstraint("units_required > 0", name="units_required_positive"),
        sa.CheckConstraint("units_fulfilled >= 0", name="units_fulfilled_non_negative"),
        # The status must agree with the arithmetic. Recomputation happens in one
        # service function, but this constraint means that if any other path ever writes
        # these columns the database rejects a combination that would make the request
        # list lie about which requests still need donors.
        sa.CheckConstraint(
            "(status = 'open' AND units_fulfilled = 0) "
            "OR (status = 'partially_fulfilled' "
            "AND units_fulfilled > 0 AND units_fulfilled < units_required) "
            "OR (status = 'fulfilled' AND units_fulfilled >= units_required)",
            name="status_matches_units",
        ),
        sa.Index("ix_blood_requests_status", "status"),
        sa.Index("ix_blood_requests_blood_group_status", "blood_group", "status"),
        sa.Index("ix_blood_requests_created_by_user_id", "created_by_user_id"),
    )

    @property
    def units_outstanding(self) -> int:
        return max(self.units_required - self.units_fulfilled, 0)

    def __repr__(self) -> str:
        return (
            f"<BloodRequest id={self.id} group={self.blood_group.value} "
            f"{self.units_fulfilled}/{self.units_required} {self.status.value}>"
        )
