"""A donor's notification inbox, and responding to a broadcast."""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..api.errors import NotFound
from ..models import BloodRequest, Notification, RequestStatus
from ..schemas.common import PageParams


def inbox_for_donor(
    session: Session, donor_id: int, params: PageParams, unanswered_only: bool = False
) -> Tuple[List[dict], int]:
    """The broadcasts sent to one donor, with the request details joined in.

    One query with a join rather than fetching notifications and then a request per row.
    An inbox of twenty five appeals would otherwise cost twenty six queries.
    """

    conditions = [Notification.donor_id == donor_id]
    if unanswered_only:
        conditions.append(Notification.responded.is_(False))

    where = sa.and_(*conditions)

    total = (
        session.scalar(sa.select(sa.func.count()).select_from(Notification).where(where)) or 0
    )

    rows = session.execute(
        sa.select(Notification, BloodRequest)
        .join(BloodRequest, BloodRequest.id == Notification.request_id)
        .where(where)
        # Unanswered first, then most recent. A donor opening the inbox should see what
        # still needs an answer above appeals they have already dealt with.
        .order_by(
            Notification.responded.asc(),
            Notification.sent_at.desc(),
            Notification.id.desc(),
        )
        .limit(params.page_size)
        .offset(params.offset)
    ).all()

    return [_serialise_inbox_row(n, r) for n, r in rows], total


def _serialise_inbox_row(notification: Notification, request: BloodRequest) -> dict:
    return {
        "id": notification.id,
        "request_id": request.id,
        "sent_at": notification.sent_at.isoformat(),
        "responded": notification.responded,
        "response_at": (
            notification.response_at.isoformat() if notification.response_at else None
        ),
        "patient_name": request.patient_name,
        "blood_group": request.blood_group.value,
        "hospital": request.hospital,
        "place": request.place,
        "contact_phone": request.contact_phone,
        "units_required": request.units_required,
        "units_fulfilled": request.units_fulfilled,
        "units_outstanding": request.units_outstanding,
        "needed_by_date": request.needed_by_date.isoformat(),
        "request_status": request.status.value,
    }


def get_notification(session: Session, notification_id: int) -> Notification:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise NotFound("No notification with that id.")
    return notification


def record_response(session: Session, notification: Notification) -> Notification:
    """Mark a broadcast as answered.

    Idempotent: responding twice leaves the original timestamp alone. Overwriting it would
    move the recorded response time later every time a donor reopened the message, which
    would quietly corrupt any measure of how quickly donors answer.

    A declined offer is recorded as a response too. Someone who read the appeal and
    answered "not this time" has responded; counting only the yeses would understate the
    response rate and overstate how many donors are ignoring notifications.
    """

    if not notification.responded:
        notification.responded = True
        notification.response_at = sa.func.now()
        session.flush()
    return notification


def list_for_request(session: Session, request_id: int) -> List[dict]:
    rows: Sequence[Notification] = session.scalars(
        sa.select(Notification)
        .where(Notification.request_id == request_id)
        .order_by(Notification.sent_at.desc(), Notification.id.desc())
    ).all()

    return [
        {
            "id": n.id,
            "donor_id": n.donor_id,
            "request_id": n.request_id,
            "sent_at": n.sent_at.isoformat(),
            "responded": n.responded,
            "response_at": n.response_at.isoformat() if n.response_at else None,
            "channel": n.channel.value,
            "delivery_error": n.delivery_error,
        }
        for n in rows
    ]
