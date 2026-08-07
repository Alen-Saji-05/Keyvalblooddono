"""The donor registry."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import BloodGroup, DonorStatus, Sex
from .types import pg_enum

if TYPE_CHECKING:
    from .donation import Donation
    from .notification import Notification
    from .user import User


class Donor(Base, TimestampMixin):
    """A person registered as willing to give blood.

    Beyond the fields named in the brief this table carries ``sex``, ``date_of_birth``,
    and ``weight_kg``. The brief asks for "any fields needed to compute medical
    eligibility", and those three are what the standard whole blood criteria are
    expressed in: the inter-donation interval differs by sex, donors must be between 18
    and 65, and there is a minimum body weight. Without them the system could check
    only availability and would happily broadcast to someone who is medically barred
    from donating.

    Note that these are eligibility inputs, not registration barriers. A seventeen year
    old or an underweight donor can be registered and simply computes as ineligible
    until that changes. Refusing the registration outright would lose the record.
    """

    __tablename__ = "donors"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    blood_group: Mapped[BloodGroup] = mapped_column(
        pg_enum(BloodGroup, "blood_group"), nullable=False
    )
    sex: Mapped[Sex] = mapped_column(pg_enum(Sex, "sex"), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(sa.Date, nullable=False)

    # Numeric rather than float: body weight sits directly in an eligibility comparison
    # against a threshold, and binary floating point makes a value entered as 45.0
    # capable of comparing below 45.
    weight_kg: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False)

    phone: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    place: Mapped[str] = mapped_column(sa.String(120), nullable=False)

    last_donation_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)

    status: Mapped[DonorStatus] = mapped_column(
        pg_enum(DonorStatus, "donor_status"),
        nullable=False,
        server_default=DonorStatus.AVAILABLE.value,
    )

    # Free-text elaboration on an unavailable status, for example the destination of a
    # move or the expected return date from travel. The reason itself lives in the
    # status; this is only the detail a human wants to read alongside it.
    status_note: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)

    donations: Mapped[List["Donation"]] = relationship(
        back_populates="donor", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="donor", cascade="all, delete-orphan", passive_deletes=True
    )
    user: Mapped[Optional["User"]] = relationship(back_populates="donor", uselist=False)

    __table_args__ = (
        sa.CheckConstraint("weight_kg > 0", name="weight_positive"),
        # A phone number identifies a donor in practice, and a duplicate registration
        # would be broadcast to twice and counted twice in the eligible-donor figure.
        sa.UniqueConstraint("phone", name="uq_donors_phone"),
        # Email is optional, so uniqueness is enforced only over the rows that have one.
        # A plain unique constraint would be satisfied by many NULLs anyway, but the
        # partial index states the intent and stays correct if the column later becomes
        # mandatory.
        sa.Index(
            "ix_donors_email_unique",
            "email",
            unique=True,
            postgresql_where=sa.text("email IS NOT NULL"),
        ),
        # The broadcast selector and the eligible-donor count both filter on blood
        # group, then availability, then the cooldown window. A composite index in that
        # order serves the whole predicate from one structure.
        sa.Index(
            "ix_donors_blood_group_status_last_donation",
            "blood_group",
            "status",
            "last_donation_date",
        ),
        # Place is matched case-insensitively, so the index has to be on the same
        # expression the query uses or it will not be consulted.
        sa.Index("ix_donors_place_lower", sa.text("lower(place)")),
    )

    def __repr__(self) -> str:
        return f"<Donor id={self.id} name={self.name!r} group={self.blood_group.value}>"
