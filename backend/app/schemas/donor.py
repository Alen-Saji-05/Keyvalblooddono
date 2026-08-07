"""Donor request and response schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from ..models.enums import BloodGroup, DonorStatus, Sex
from .base import ApiModel, OutModel
from .common import PageParams
from .validators import validate_past_date, validate_phone


class DonorCreateIn(ApiModel):
    """A donor registered by an administrator.

    The same fields a donor supplies when self-registering, minus the account. An admin
    registering someone who walked into a drive should not have to invent a password for
    them; a login can be attached later through the user endpoints if the donor wants one.
    """

    name: str = Field(min_length=2, max_length=120)
    blood_group: BloodGroup
    sex: Sex
    date_of_birth: date
    weight_kg: Decimal = Field(gt=0, le=500, decimal_places=2)
    phone: str = Field(min_length=7, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    place: str = Field(min_length=2, max_length=120)
    last_donation_date: Optional[date] = None

    _check_phone = field_validator("phone")(validate_phone)

    @field_validator("date_of_birth")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        validate_past_date(value)
        if value.year < date.today().year - 120:
            raise ValueError("Check the year of birth.")
        return value

    @field_validator("last_donation_date")
    @classmethod
    def _check_last_donation(cls, value: Optional[date]) -> Optional[date]:
        return value if value is None else validate_past_date(value)


class DonorUpdateIn(ApiModel):
    """Editable donor details.

    Blood group and sex are absent on purpose. Both are inputs to the eligibility rule and
    neither changes in practice, so allowing them to be patched would mostly serve to let
    a typo silently alter who gets broadcast to. Correcting a genuine error in either is a
    deliberate act for an administrator, handled by editing the record directly.

    Availability is also absent: it has its own endpoint, because changing it carries a
    reason and is the one donor field that changes often.
    """

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    weight_kg: Optional[Decimal] = Field(default=None, gt=0, le=500, decimal_places=2)
    phone: Optional[str] = Field(default=None, min_length=7, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    place: Optional[str] = Field(default=None, min_length=2, max_length=120)
    last_donation_date: Optional[date] = None

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: Optional[str]) -> Optional[str]:
        return value if value is None else validate_phone(value)

    @field_validator("last_donation_date")
    @classmethod
    def _check_last_donation(cls, value: Optional[date]) -> Optional[date]:
        return value if value is None else validate_past_date(value)

    @model_validator(mode="after")
    def _require_a_change(self) -> "DonorUpdateIn":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("Provide at least one field to change.")
        return self


class DonorStatusIn(ApiModel):
    """Marking a donor available or unavailable, with the reason.

    The reason is the status. A note may accompany an unavailable status but cannot stand
    in for one, and a note on an available donor is rejected rather than stored where
    nothing will ever display it.
    """

    status: DonorStatus
    note: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _note_only_when_unavailable(self) -> "DonorStatusIn":
        if self.status is DonorStatus.AVAILABLE and self.note:
            raise ValueError("A note applies only when marking a donor unavailable.")
        return self


class DonorSearchParams(PageParams):
    """Filters for the donor directory.

    ``eligible_only`` is the filter that matters operationally: available and eligible are
    not the same thing, and a coordinator looking for someone to call wants the second.
    """

    blood_group: Optional[BloodGroup] = None
    place: Optional[str] = Field(default=None, max_length=120)
    status: Optional[DonorStatus] = None
    eligible_only: bool = False
    q: Optional[str] = Field(default=None, max_length=120)


class DonorOut(OutModel):
    """A donor as returned to an administrator or to the donor themselves.

    Eligibility is computed and returned rather than left for the client to derive. The
    rule involves the donor's sex, age, weight, availability, and cooldown, and a client
    reimplementing it would eventually disagree with the server about who can donate.
    """

    id: int
    name: str
    blood_group: BloodGroup
    sex: Sex
    date_of_birth: date
    age: int
    weight_kg: Decimal
    phone: str
    email: Optional[str]
    place: str
    last_donation_date: Optional[date]
    status: DonorStatus
    status_note: Optional[str]
    is_eligible: bool
    ineligibility_reasons: List[str]
    next_eligible_date: Optional[date]
    created_at: datetime


class AvailabilityCountOut(OutModel):
    """One row of the aggregate availability view.

    This is what a patient sees instead of the donor directory: how many eligible donors
    exist for a blood group, with no identities. It answers whether filing a request has
    any prospect of being met without disclosing who the donors are.
    """

    blood_group: BloodGroup
    eligible_donors: int
    total_donors: int
