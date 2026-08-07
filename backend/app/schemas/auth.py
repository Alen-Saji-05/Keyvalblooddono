"""Request and response schemas for authentication."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional, Union

from pydantic import EmailStr, Field, field_validator

from ..models.enums import BloodGroup, Sex, UserRole
from .base import ApiModel, OutModel
from .validators import validate_past_date, validate_phone


class LoginIn(ApiModel):
    email: EmailStr
    # No length constraint on login. Enforcing the policy here would reject an account
    # created before the policy changed and, more importantly, would tell an attacker
    # which length range is worth trying.
    password: str


class _RegistrationBase(ApiModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=2, max_length=120)


class PatientRegistrationIn(_RegistrationBase):
    """Someone who needs blood. No donor record is created."""

    role: Literal[UserRole.PATIENT]


class DonorRegistrationIn(_RegistrationBase):
    """Someone offering to give blood.

    Registration creates both the account and the donor record in one transaction, so a
    donor cannot end up with a login and nothing to manage.

    The eligibility inputs are captured here but none of them block registration. A
    person below the minimum weight or outside the age range is registered and simply
    computes as ineligible until that changes, because refusing the sign-up would throw
    away a donor who may qualify in six months.
    """

    role: Literal[UserRole.DONOR]

    blood_group: BloodGroup
    sex: Sex
    date_of_birth: date
    weight_kg: Decimal = Field(gt=0, le=500, decimal_places=2)
    phone: str = Field(min_length=7, max_length=20)
    place: str = Field(min_length=2, max_length=120)
    last_donation_date: Optional[date] = None

    _check_phone = field_validator("phone")(validate_phone)

    @field_validator("date_of_birth")
    @classmethod
    def _check_date_of_birth(cls, value: date) -> date:
        validate_past_date(value)
        # An upper bound on age catches a mistyped year, which would otherwise be stored
        # and quietly excluded from every broadcast by the age rule.
        if value.year < date.today().year - 120:
            raise ValueError("Check the year of birth.")
        return value

    _check_last_donation = field_validator("last_donation_date")(
        lambda cls, v: v if v is None else validate_past_date(v)
    )


RegistrationIn = Union[PatientRegistrationIn, DonorRegistrationIn]

# One model per role, selected by an explicit lookup on the submitted role.
#
# The obvious alternative is a Pydantic discriminated union, which does the dispatch
# automatically. It was tried and rejected: Pydantic prefixes every error location with
# the variant tag, so a missing name comes back keyed as "patient.full_name" rather than
# "full_name", and the registration form cannot attach the message to its field without
# knowing to strip a prefix. An explicit lookup costs four lines and keeps error
# locations equal to field names.
#
# One model with optional donor fields was also rejected: a patient could then post a
# blood group and have it silently ignored, and a donor could omit a required one and
# only discover it at the database.
REGISTRATION_MODELS = {
    UserRole.PATIENT.value: PatientRegistrationIn,
    UserRole.DONOR.value: DonorRegistrationIn,
}


def registration_model_for(role: object) -> type:
    """Pick the registration schema for a submitted role.

    Anything other than donor or patient is refused here, which is what makes the
    administrator role unreachable from the public endpoint. There is no field a caller
    can set to escalate, because the escalated value never selects a model.
    """

    from ..api.errors import UnprocessableEntity

    model = REGISTRATION_MODELS.get(role) if isinstance(role, str) else None
    if model is None:
        raise UnprocessableEntity(
            "Registration is available for donor and patient accounts only.",
            details={"fields": {"role": ["Choose either 'donor' or 'patient'."]}},
        )
    return model


class PasswordChangeIn(ApiModel):
    current_password: str
    new_password: str


class UserOut(OutModel):
    """The account as returned to a client. There is no password field of any kind."""

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    donor_id: Optional[int] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None


class LoginOut(OutModel):
    """The login response.

    Carries the access token only. The refresh token is never in the body; it is set as
    an httpOnly cookie the JavaScript cannot read, so a script that manages to read this
    response still does not obtain long-lived credentials.
    """

    access_token: str
    # Seconds until the access token expires, so the client can schedule a refresh rather
    # than decoding the token or waiting to be rejected.
    expires_in: int
    user: UserOut
