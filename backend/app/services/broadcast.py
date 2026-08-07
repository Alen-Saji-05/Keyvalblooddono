"""Selecting eligible donors for a request and notifying them."""

from __future__ import annotations

import logging
from typing import List

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..api.errors import ApiError
from ..models import BloodRequest, Donor, Notification, RequestStatus
from ..notifications import get_notifier
from ..schemas.request import BroadcastIn
from .compatibility import acceptable_donor_groups
from .eligibility import eligibility_clause

logger = logging.getLogger(__name__)


def broadcast_request(
    session: Session, request: BloodRequest, options: BroadcastIn
) -> dict:
    """Notify every eligible donor who has not already been told about this request.

    Selection is the eligibility predicate from ``services.eligibility`` intersected with
    the acceptable blood groups, and optionally narrowed by place. Using the shared
    predicate rather than an inline copy is what keeps this in step with the eligible
    donor count on the dashboard and with the eligible filter in the donor directory.
    """

    if request.status is RequestStatus.FULFILLED:
        # Refused rather than allowed as a no-op. Broadcasting a met request sends people
        # to a hospital that no longer needs them, which wastes a donation that could have
        # gone to an open request and costs the network credibility with its donors.
        raise ApiError(
            "This request is already fulfilled. Broadcasting would send donors to a "
            "hospital that no longer needs them.",
            status_code=409,
            code="request_already_fulfilled",
        )

    groups = acceptable_donor_groups(request.blood_group, options.include_compatible)

    conditions = [Donor.blood_group.in_(groups), eligibility_clause()]
    if options.place:
        conditions.append(
            sa.func.lower(Donor.place).like(f"{options.place.strip().lower()}%")
        )

    eligible = session.scalars(
        sa.select(Donor).where(sa.and_(*conditions)).order_by(Donor.id)
    ).all()

    already_notified_ids = set(
        session.scalars(
            sa.select(Notification.donor_id).where(Notification.request_id == request.id)
        ).all()
    )

    # Donors already told about this request are skipped rather than notified again.
    # Re-broadcasting a request still short of units is normal, and without this a second
    # broadcast would send a duplicate message and add a second row that inflates the
    # denominator of the response rate. The unique constraint on (donor_id, request_id)
    # would reject the row anyway; this turns a would-be error into the intended
    # behaviour.
    recipients = [donor for donor in eligible if donor.id not in already_notified_ids]

    notifier = get_notifier()
    delivery_failures = 0

    for donor in recipients:
        notification = Notification(
            donor_id=donor.id,
            request_id=request.id,
            channel=notifier.channel,
        )

        try:
            notifier.send(donor, request)
        except Exception as exc:  # noqa: BLE001
            # One donor's delivery failure must not abort a broadcast to everyone else,
            # and it must not discard the notification: the record is what the donor's
            # inbox reads and what the response rate counts, so the outreach still
            # happened even if the message bounced. The reason is stored so it can be
            # diagnosed rather than guessed at.
            delivery_failures += 1
            notification.delivery_error = f"{type(exc).__name__}: {exc}"[:500]
            logger.warning(
                "Notification delivery failed for donor %s on request %s: %s",
                donor.id,
                request.id,
                exc,
            )

        session.add(notification)

    session.flush()

    return {
        "request_id": request.id,
        "notified": len(recipients),
        "already_notified": len(already_notified_ids),
        "eligible_total": len(eligible),
        "delivery_failures": delivery_failures,
        "targeted_blood_groups": sorted(group.value for group in groups),
    }
