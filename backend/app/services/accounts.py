"""Account creation, authentication, and password changes."""

from __future__ import annotations

import logging
from typing import Optional, Union

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..api.errors import Conflict, NotFound, Unauthorised, UnprocessableEntity
from ..models import Donor, DonorStatus, User, UserRole
from ..schemas.auth import DonorRegistrationIn, PatientRegistrationIn
from ..schemas.user import AdminUserCreateIn
from ..schemas.validators import validate_password
from ..security.passwords import hash_password, needs_rehash, verify_password

logger = logging.getLogger(__name__)

# Verified against when no account matches the submitted address. Argon2 is deliberately
# slow, so returning early on an unknown address would make "no such account" measurably
# faster than "wrong password" and turn the login endpoint into an account enumeration
# oracle. Hashing a throwaway value keeps both paths the same shape.
_DUMMY_HASH = hash_password("timing-equalisation-placeholder")


def normalise_email(email: str) -> str:
    """Lower-case and strip.

    Applied on write and on lookup, so the two cannot disagree. Treating addresses
    case-sensitively would let the same person register twice and then fail to log in
    with the capitalisation they remember.
    """

    return email.strip().lower()


def find_by_email(session: Session, email: str) -> Optional[User]:
    return session.scalar(sa.select(User).where(User.email == normalise_email(email)))


def register_account(
    session: Session, payload: Union[DonorRegistrationIn, PatientRegistrationIn]
) -> User:
    """Create a self-registered donor or patient account.

    A donor gets an account and a donor record in one transaction. Creating the account
    first and the record afterwards would leave a donor logged in with nothing to manage
    if the second write failed.

    The role is taken from the payload's discriminated variant, not from a free-form
    field, so there is no path by which a request can register itself as an
    administrator.
    """

    email = normalise_email(payload.email)
    validate_password(payload.password, email=email)

    if find_by_email(session, email) is not None:
        # The address is disclosed as taken, which is unavoidable: a registration form
        # that accepted a duplicate silently would be unusable. The login endpoint, where
        # enumeration actually matters, does not disclose it.
        raise Conflict("An account already exists for that email address.")

    if isinstance(payload, DonorRegistrationIn):
        existing_phone = session.scalar(
            sa.select(Donor).where(Donor.phone == payload.phone)
        )
        if existing_phone is not None:
            raise Conflict("A donor is already registered with that phone number.")

        donor = Donor(
            name=payload.full_name,
            blood_group=payload.blood_group,
            sex=payload.sex,
            date_of_birth=payload.date_of_birth,
            weight_kg=payload.weight_kg,
            phone=payload.phone,
            email=email,
            place=payload.place,
            last_donation_date=payload.last_donation_date,
            status=DonorStatus.AVAILABLE,
        )
        session.add(donor)
        session.flush()
        donor_id = donor.id
        role = UserRole.DONOR
    else:
        donor_id = None
        role = UserRole.PATIENT

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        donor_id=donor_id,
    )
    session.add(user)
    session.flush()
    return user


def create_user_as_admin(session: Session, payload: AdminUserCreateIn) -> User:
    """Create an account on behalf of an administrator, of any role."""

    email = normalise_email(payload.email)
    validate_password(payload.password, email=email)

    if find_by_email(session, email) is not None:
        raise Conflict("An account already exists for that email address.")

    if payload.role is UserRole.DONOR:
        donor = session.get(Donor, payload.donor_id)
        if donor is None:
            raise NotFound("No donor record with that id.")
        already_linked = session.scalar(
            sa.select(User).where(User.donor_id == payload.donor_id)
        )
        if already_linked is not None:
            raise Conflict("That donor record already has an account.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        donor_id=payload.donor_id,
    )
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    """Verify credentials and return the account.

    Every failure - unknown address, wrong password, deactivated account - raises the
    same message. Distinguishing them would let anyone test whether a given person is
    registered with this network, which for a medical service is itself disclosure.

    A successful verification against an outdated hash is rehashed in place, so accounts
    are upgraded to current Argon2 parameters as people sign in rather than needing a
    forced reset.
    """

    generic = "Email or password is incorrect."

    user = find_by_email(session, email)

    if user is None:
        verify_password(_DUMMY_HASH, password)
        raise Unauthorised(generic)

    if not verify_password(user.password_hash, password):
        raise Unauthorised(generic)

    if not user.is_active:
        raise Unauthorised(generic)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = sa.func.now()
    return user


def change_password(session: Session, user: User, current: str, new: str) -> None:
    """Change a signed-in user's own password.

    The current password is required even though the caller is already authenticated: it
    is what stops someone at an unattended logged-in browser from taking the account.
    """

    if not verify_password(user.password_hash, current):
        raise Unauthorised("The current password is incorrect.")

    if current == new:
        raise UnprocessableEntity(
            "The new password must differ from the current one.",
            details={"fields": {"new_password": ["Choose a different password."]}},
        )

    validate_password(new, email=user.email)
    user.password_hash = hash_password(new)
    session.flush()
