"""Donor self-service.

Everything here is scoped to the authenticated donor by construction. The routes take no
donor id at all, so there is no parameter to tamper with and no ownership check that can
be forgotten - the only donor these endpoints can reach is the one on the token.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..api.errors import Forbidden
from ..extensions import db
from ..models import UserRole
from ..schemas.common import PageParams, paginated
from ..schemas.donor import DonorStatusIn, DonorUpdateIn
from ..security.rbac import current_user, roles_required
from ..services import donations as donation_service
from ..services import donors as donor_service
from ..services import notifications as notification_service
from .parsing import parse_body, parse_query

bp = Blueprint("me", __name__)


def _own_donor():
    user = current_user()
    if user.role is not UserRole.DONOR or user.donor_id is None:
        raise Forbidden("This endpoint is for donor accounts.")
    return donor_service.get_donor(db.session, user.donor_id)


@bp.get("/donor")
@roles_required(UserRole.DONOR)
def my_donor_record():
    return jsonify(donor_service.serialise_donor(_own_donor()))


@bp.patch("/donor")
@roles_required(UserRole.DONOR)
def update_my_donor_record():
    payload = parse_body(DonorUpdateIn)
    donor = _own_donor()
    donor_service.update_donor(db.session, donor, payload)
    db.session.commit()
    return jsonify(donor_service.serialise_donor(donor))


@bp.patch("/donor/status")
@roles_required(UserRole.DONOR)
def update_my_availability():
    """Set your own availability, with a reason.

    The donor knows they are travelling next month; the administrator does not. Letting
    donors maintain this themselves is most of the value of giving them accounts, and it
    keeps the eligible-donor figure honest.
    """

    payload = parse_body(DonorStatusIn)
    donor = _own_donor()
    donor_service.set_status(db.session, donor, payload)
    db.session.commit()
    return jsonify(donor_service.serialise_donor(donor))


@bp.get("/notifications")
@roles_required(UserRole.DONOR)
def my_notifications():
    """Broadcasts sent to this donor, unanswered ones first."""

    params = parse_query(PageParams)
    unanswered_only = request.args.get("unanswered_only", "").lower() in {"1", "true", "yes"}

    user = current_user()
    items, total = notification_service.inbox_for_donor(
        db.session, user.donor_id, params, unanswered_only
    )
    return jsonify(paginated(items, total, params))


@bp.get("/donations")
@roles_required(UserRole.DONOR)
def my_donations():
    user = current_user()
    return jsonify(
        {"items": donation_service.list_donations_for_donor(db.session, user.donor_id)}
    )
