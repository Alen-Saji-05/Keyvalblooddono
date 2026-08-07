"""Responding to a broadcast."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..api.errors import Forbidden
from ..extensions import db
from ..models import UserRole
from ..schemas.request import NotificationRespondIn
from ..security.rbac import current_user, roles_required
from ..services import notifications as notification_service
from .parsing import json_body, parse_body

bp = Blueprint("notifications", __name__)


@bp.post("/<int:notification_id>/respond")
@roles_required(UserRole.DONOR, UserRole.ADMIN)
def respond(notification_id: int):
    """Record that a donor answered a broadcast.

    A donor may answer their own; an administrator may record a response on a donor's
    behalf, which is how a phone call gets into the figures. Without that, the response
    rate would only ever count people who used the portal and would understate a network
    where most donors answer by telephone.

    Recording a decline counts as a response too. Someone who read the appeal and said
    "not this time" has responded; counting only the yeses would understate the response
    rate and overstate how many donors ignore notifications.
    """

    from flask import request as flask_request

    payload = (
        parse_body(NotificationRespondIn, json_body())
        if flask_request.is_json and flask_request.get_data()
        else NotificationRespondIn()
    )

    notification = notification_service.get_notification(db.session, notification_id)

    user = current_user()
    if user.role is UserRole.DONOR and notification.donor_id != user.donor_id:
        raise Forbidden("This notification was sent to another donor.")

    notification_service.record_response(db.session, notification)
    db.session.commit()

    return jsonify(
        {
            "id": notification.id,
            "request_id": notification.request_id,
            "responded": notification.responded,
            "response_at": (
                notification.response_at.isoformat() if notification.response_at else None
            ),
            "willing": payload.willing,
        }
    )
