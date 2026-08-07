"""Administrator management of accounts.

Mounted at ``/api/users`` rather than ``/api/auth/users``. Accounts are a resource that
happens to be managed by administrators, not an operation on the caller's own session,
and the ``/api/auth`` prefix is reserved for the latter.
"""

from __future__ import annotations

import sqlalchemy as sa
from flask import Blueprint, jsonify

from ..api.errors import Forbidden, NotFound
from ..extensions import db
from ..models import User, UserRole
from ..schemas.auth import UserOut
from ..schemas.user import AdminUserCreateIn, AdminUserUpdateIn
from ..security.rbac import admin_required, current_user
from ..services import accounts
from .parsing import parse_body

bp = Blueprint("users", __name__)


def _serialise(user: User) -> dict:
    return UserOut.model_validate(user).model_dump(mode="json")


@bp.get("")
@admin_required
def list_users():
    users = db.session.scalars(sa.select(User).order_by(User.created_at.desc())).all()
    return jsonify({"items": [_serialise(u) for u in users], "total": len(users)})


@bp.post("")
@admin_required
def create_user():
    payload = parse_body(AdminUserCreateIn)
    user = accounts.create_user_as_admin(db.session, payload)
    db.session.commit()
    return jsonify(_serialise(user)), 201


@bp.get("/<int:user_id>")
@admin_required
def get_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFound("No account with that id.")
    return jsonify(_serialise(user))


@bp.patch("/<int:user_id>")
@admin_required
def update_user(user_id: int):
    """Rename, change role between admin and patient, or deactivate an account."""

    payload = parse_body(AdminUserUpdateIn)
    target = db.session.get(User, user_id)
    if target is None:
        raise NotFound("No account with that id.")

    actor = current_user()

    # An administrator cannot deactivate or demote their own account. The intent is not
    # to protect them from a mistake so much as to stop the last administrator removing
    # the only account that can create another one, which leaves the system with no way
    # to broadcast a request and no way back in short of the CLI.
    if target.id == actor.id:
        if payload.is_active is False:
            raise Forbidden("You cannot deactivate your own account.")
        if payload.role is not None and payload.role is not UserRole.ADMIN:
            raise Forbidden("You cannot change your own role.")

    if target.role is UserRole.DONOR and payload.role is not None:
        raise Forbidden(
            "A donor account cannot change role, because it is tied to a donor record."
        )

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active

    db.session.commit()
    return jsonify(_serialise(target))
