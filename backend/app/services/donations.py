"""Recording donations against a request."""

from __future__ import annotations

from typing import List, Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..api.errors import ApiError, NotFound
from ..models import BloodRequest, Donation, Donor, Notification, User
from ..schemas.request import DonationCreateIn
from .fulfilment import lock_request, recompute_request_fulfilment


def record_donation(
    session: Session, request: BloodRequest, payload: DonationCreateIn, recorded_by: User
) -> Donation:
    """Record one donor giving units towards one request.

    Everything happens in one transaction, and the order is load-bearing.

    The exclusive lock on the request is taken **first**, before the donation is
    inserted. Inserting a donation takes a key-share lock on its parent request, so two
    administrators who each inserted first and then asked for the exclusive lock would
    each be waiting on a lock the other holds. That is a deadlock, and it was one until
    this ordering was fixed. Locking first gives every writer the same lock order.

    Fulfilment is recomputed after the insert, so the total includes the donation just
    recorded.
    """

    # Serialise concurrent writers on this request before touching anything.
    lock_request(session, request.id)

    donor = session.get(Donor, payload.donor_id)
    if donor is None:
        raise NotFound("No donor with that id.")

    if payload.donation_date < request.created_at.date():
        # A donation dated before the request was filed cannot have been given in
        # response to it. Usually a mistyped year, and it would otherwise sit in the
        # history as a donation that answered an appeal that did not yet exist.
        raise ApiError(
            "The donation date is before this request was created.",
            status_code=422,
            code="validation_error",
            details={"fields": {"donation_date": ["Check the date."]}},
        )

    donation = Donation(
        donor_id=donor.id,
        request_id=request.id,
        units_given=payload.units_given,
        donation_date=payload.donation_date,
        recorded_by_user_id=recorded_by.id,
        notes=payload.notes,
    )
    session.add(donation)
    session.flush()

    recompute_request_fulfilment(session, request.id)

    # The donor's cooldown starts from their most recent donation. Guarded with a
    # comparison rather than assigned outright, because an administrator entering a
    # backlog of paper records out of order would otherwise move the date backwards and
    # make a donor look eligible months before they are.
    if donor.last_donation_date is None or payload.donation_date > donor.last_donation_date:
        donor.last_donation_date = payload.donation_date

    # A donor who actually gave has, by any reasonable definition, responded to the
    # broadcast. Marking it here means the response rate counts people who turned up and
    # not only those who clicked a button, which is the figure the network cares about.
    notification = session.scalar(
        sa.select(Notification).where(
            Notification.donor_id == donor.id,
            Notification.request_id == request.id,
            Notification.responded.is_(False),
        )
    )
    if notification is not None:
        notification.responded = True
        notification.response_at = sa.func.now()

    session.flush()
    return donation


def list_donations_for_request(
    session: Session, request_id: int, include_donor_names: bool
) -> List[dict]:
    """Donations against one request.

    ``include_donor_names`` is false for a patient. They see that three people gave two
    units on given dates, which is the progress information they need, without the
    identities of donors who never consented to being named to them. An administrator
    sees the names, because contacting donors is their job.
    """

    rows = session.execute(
        sa.select(Donation, Donor.name)
        .join(Donor, Donor.id == Donation.donor_id)
        .where(Donation.request_id == request_id)
        .order_by(Donation.donation_date.asc(), Donation.id.asc())
    ).all()

    return [
        {
            "id": donation.id,
            "donor_id": donation.donor_id if include_donor_names else None,
            "donor_name": donor_name if include_donor_names else None,
            "request_id": donation.request_id,
            "units_given": donation.units_given,
            "donation_date": donation.donation_date.isoformat(),
            "notes": donation.notes if include_donor_names else None,
            "created_at": donation.created_at.isoformat(),
        }
        for donation, donor_name in rows
    ]


def list_donations_for_donor(session: Session, donor_id: int) -> List[dict]:
    donations: Sequence[Donation] = session.scalars(
        sa.select(Donation)
        .where(Donation.donor_id == donor_id)
        .order_by(Donation.donation_date.desc(), Donation.id.desc())
    ).all()

    return [
        {
            "id": d.id,
            "donor_id": d.donor_id,
            "donor_name": None,
            "request_id": d.request_id,
            "units_given": d.units_given,
            "donation_date": d.donation_date.isoformat(),
            "notes": d.notes,
            "created_at": d.created_at.isoformat(),
        }
        for d in donations
    ]
