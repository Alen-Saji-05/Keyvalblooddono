"""Network analytics."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..api.errors import Forbidden
from ..extensions import db
from ..models import UserRole
from ..security.rbac import authenticated, current_user
from ..services import summary as summary_service

bp = Blueprint("summary", __name__)


@bp.get("")
@authenticated
def get_summary():
    """The network summary, scoped to the caller.

    An administrator gets the whole network. A patient gets the same shape computed over
    their own requests only, with the donor counts left network-wide because those are
    aggregate, carry no identities, and are exactly what tells a patient whether their
    request has any prospect of being met.

    Donors get no summary. Their view of the network is their own inbox and their own
    donation history; a donor has no reason to see how many requests are going unmet
    across the whole network, and it would be a discouraging and slightly alarming figure
    to publish to the people the network depends on.
    """

    user = current_user()

    if user.role is UserRole.ADMIN:
        return jsonify(summary_service.network_summary(db.session))

    if user.role is UserRole.PATIENT:
        return jsonify(summary_service.patient_summary(db.session, user.id))

    raise Forbidden("The network summary is not available to donor accounts.")
