"""The network summary."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..models import (
    BloodRequest,
    Donation,
    Donor,
    DonorStatus,
    Notification,
    RequestStatus,
)
from ..models.enums import BloodGroup
from .eligibility import eligibility_clause


def _rate(numerator: int, denominator: int) -> float:
    """A percentage, or zero when nothing has been sent.

    Returning 0.0 rather than None for an empty denominator, because every caller renders
    this as a number and a null would have each of them inventing its own placeholder. A
    network that has sent no broadcasts has a response rate of zero in the only sense that
    matters: nobody has responded.
    """

    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def network_summary(session: Session) -> dict:
    """The four figures the brief asks for, computed across the whole network."""

    donation_count, units_donated = session.execute(
        sa.select(
            sa.func.count(Donation.id),
            sa.func.coalesce(sa.func.sum(Donation.units_given), 0),
        )
    ).one()

    # One grouped query rather than a count per status. Three round trips to produce three
    # numbers off the same table is wasteful, and the totals cannot disagree if they come
    # from one scan.
    status_rows = session.execute(
        sa.select(BloodRequest.status, sa.func.count()).group_by(BloodRequest.status)
    ).all()
    by_status = {status: count for status, count in status_rows}

    fulfilled = by_status.get(RequestStatus.FULFILLED, 0)
    partial = by_status.get(RequestStatus.PARTIALLY_FULFILLED, 0)
    open_count = by_status.get(RequestStatus.OPEN, 0)

    notifications_sent, notifications_responded = session.execute(
        sa.select(
            sa.func.count(Notification.id),
            sa.func.count(Notification.id).filter(Notification.responded.is_(True)),
        )
    ).one()

    donors_registered, donors_available, donors_eligible = session.execute(
        sa.select(
            sa.func.count(Donor.id),
            sa.func.count(Donor.id).filter(Donor.status == DonorStatus.AVAILABLE),
            # The same predicate the broadcast selector uses. This is the whole reason
            # eligibility is defined once: a dashboard figure that disagreed with who
            # actually gets notified would be worse than no figure at all.
            sa.func.count(Donor.id).filter(eligibility_clause()),
        )
    ).one()

    return {
        "scope": "network",
        "total_donations": donation_count,
        "total_units_donated": int(units_donated),
        "requests_total": fulfilled + partial + open_count,
        "requests_fulfilled": fulfilled,
        "requests_partially_fulfilled": partial,
        "requests_open": open_count,
        "requests_unfulfilled": partial + open_count,
        "notifications_sent": notifications_sent,
        "notifications_responded": notifications_responded,
        "donor_response_rate": _rate(notifications_responded, notifications_sent),
        "donors_registered": donors_registered,
        "donors_available": donors_available,
        "donors_eligible_now": donors_eligible,
        "demand_by_blood_group": _demand_by_blood_group(session),
    }


def _demand_by_blood_group(session: Session) -> list:
    """Outstanding units needed against eligible donors, per blood group.

    The operationally useful cut: a group with forty units outstanding and two eligible
    donors is the one that needs a recruitment drive, and neither number alone says that.
    Every group gets a row even at zero, because an absent row renders as missing data
    rather than as no demand.
    """

    demand_rows = session.execute(
        sa.select(
            BloodRequest.blood_group,
            sa.func.coalesce(
                sa.func.sum(BloodRequest.units_required - BloodRequest.units_fulfilled), 0
            ),
        )
        .where(BloodRequest.status != RequestStatus.FULFILLED)
        .group_by(BloodRequest.blood_group)
    ).all()
    demand = {group: int(units) for group, units in demand_rows}

    donor_rows = session.execute(
        sa.select(Donor.blood_group, sa.func.count().filter(eligibility_clause()))
        .group_by(Donor.blood_group)
    ).all()
    supply = {group: count for group, count in donor_rows}

    return [
        {
            "blood_group": group.value,
            "open_units_needed": demand.get(group, 0),
            "eligible_donors": supply.get(group, 0),
        }
        for group in BloodGroup
    ]


def patient_summary(session: Session, user_id: int) -> dict:
    """The same shape, scoped to one patient's own requests.

    Donor counts stay network-wide because they are aggregate and carry no identities, and
    they are the figures that tell a patient whether their request has any prospect of
    being met. Everything else counts only their own requests: their donations, their
    broadcasts, their response rate.
    """

    own = BloodRequest.created_by_user_id == user_id
    own_ids = sa.select(BloodRequest.id).where(own)

    donation_count, units_donated = session.execute(
        sa.select(
            sa.func.count(Donation.id),
            sa.func.coalesce(sa.func.sum(Donation.units_given), 0),
        ).where(Donation.request_id.in_(own_ids))
    ).one()

    status_rows = session.execute(
        sa.select(BloodRequest.status, sa.func.count()).where(own).group_by(BloodRequest.status)
    ).all()
    by_status = {status: count for status, count in status_rows}

    fulfilled = by_status.get(RequestStatus.FULFILLED, 0)
    partial = by_status.get(RequestStatus.PARTIALLY_FULFILLED, 0)
    open_count = by_status.get(RequestStatus.OPEN, 0)

    notifications_sent, notifications_responded = session.execute(
        sa.select(
            sa.func.count(Notification.id),
            sa.func.count(Notification.id).filter(Notification.responded.is_(True)),
        ).where(Notification.request_id.in_(own_ids))
    ).one()

    donors_registered, donors_available, donors_eligible = session.execute(
        sa.select(
            sa.func.count(Donor.id),
            sa.func.count(Donor.id).filter(Donor.status == DonorStatus.AVAILABLE),
            sa.func.count(Donor.id).filter(eligibility_clause()),
        )
    ).one()

    return {
        "scope": "own_requests",
        "total_donations": donation_count,
        "total_units_donated": int(units_donated),
        "requests_total": fulfilled + partial + open_count,
        "requests_fulfilled": fulfilled,
        "requests_partially_fulfilled": partial,
        "requests_open": open_count,
        "requests_unfulfilled": partial + open_count,
        "notifications_sent": notifications_sent,
        "notifications_responded": notifications_responded,
        "donor_response_rate": _rate(notifications_responded, notifications_sent),
        "donors_registered": donors_registered,
        "donors_available": donors_available,
        "donors_eligible_now": donors_eligible,
        "demand_by_blood_group": [],
    }
