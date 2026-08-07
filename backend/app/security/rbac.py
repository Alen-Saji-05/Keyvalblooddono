"""Role-based authorisation.

Authorisation is expressed as decorators on route functions rather than as checks inside
handler bodies. The reason is auditability: the permission for an endpoint is visible on
the line above it, and an endpoint with no decorator is conspicuously public rather than
accidentally so.

Two roles are only ever a first filter. Ownership - a patient reading their own request,
a donor answering their own notification - cannot be decided from the role alone and is
enforced in the service layer where the row is available.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask_jwt_extended import get_current_user, jwt_required

from ..api.errors import Forbidden, Unauthorised
from ..models import User, UserRole


def current_user() -> User:
    """The authenticated user.

    Raises rather than returning None. Every caller is inside a ``@jwt_required``
    endpoint, so the absence of a user is a programming error, and returning None would
    push a null check into every handler where forgetting one means an authorisation
    bypass.
    """

    user = get_current_user()
    if user is None:
        raise Unauthorised("Authentication required.")
    return user


def roles_required(*roles: UserRole) -> Callable:
    """Restrict an endpoint to the given roles.

    Applies ``@jwt_required`` itself rather than expecting it to be stacked separately.
    Requiring two decorators means an endpoint can be written with only the role check,
    which would then read from an unauthenticated context and fail open.
    """

    allowed = set(roles)

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user = current_user()
            if user.role not in allowed:
                raise Forbidden(
                    "Your account does not have permission to perform this action."
                )
            return fn(*args, **kwargs)

        # Recorded on the function so the route table can be inspected and tested, and
        # so a future audit can list every endpoint with its permitted roles.
        wrapper.__allowed_roles__ = allowed  # type: ignore[attr-defined]
        return wrapper

    return decorator


def admin_required(fn: Callable) -> Callable:
    """Restrict to administrators.

    Broadcasting and donation recording sit behind this. Broadcast sends real messages to
    real people, and donation records are what every fulfilment and analytics figure is
    computed from, so neither belongs to the beneficiary of a request.
    """

    return roles_required(UserRole.ADMIN)(fn)


def authenticated(fn: Callable) -> Callable:
    """Any signed-in account, of any role."""

    return roles_required(UserRole.ADMIN, UserRole.DONOR, UserRole.PATIENT)(fn)


def require_self_or_admin(owner_user_id: int | None) -> None:
    """Allow the owner of a row, or any administrator.

    Called from a handler once the row has been loaded, because ownership is a property
    of the data and cannot be known from the token alone.
    """

    user = current_user()
    if user.is_admin:
        return
    if owner_user_id is None or owner_user_id != user.id:
        raise Forbidden("This record belongs to another account.")


def require_own_donor_record(donor_id: int) -> None:
    """Allow an administrator, or the donor whose record this is."""

    user = current_user()
    if user.is_admin:
        return
    if user.role is not UserRole.DONOR or user.donor_id != donor_id:
        raise Forbidden("This donor record belongs to another account.")
