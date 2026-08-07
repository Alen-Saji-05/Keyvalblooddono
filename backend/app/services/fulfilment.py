"""Keeping a request's fulfilment total and status in step with its donations.

The rule the brief states is that a request is normally met by several donors, one unit
at a time, and stays open until the cumulative units reach what was asked for. That
makes ``units_fulfilled`` a running total over the donations table and ``status`` a
function of two numbers.

Both are recomputed here, in one function, on every change. Nothing else in the codebase
writes either column.
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..models import BloodRequest, Donation, RequestStatus


class RequestNotFound(Exception):
    """Raised when a fulfilment recomputation targets a request that does not exist."""


def derive_status(units_fulfilled: int, units_required: int) -> RequestStatus:
    """Map the arithmetic onto the three-state status.

    ``>=`` rather than ``==`` on the fulfilled branch: a final donation can overshoot the
    requirement, and an over-supplied request is fulfilled, not stuck in partial.
    """

    if units_fulfilled <= 0:
        return RequestStatus.OPEN
    if units_fulfilled < units_required:
        return RequestStatus.PARTIALLY_FULFILLED
    return RequestStatus.FULFILLED


def lock_request(session: Session, request_id: int) -> BloodRequest:
    """Take an exclusive row lock on a request, and return it.

    **This must be called before inserting a donation, not after.** The ordering is not a
    style preference; getting it wrong deadlocks under concurrency, and it did.

    Inserting a donation takes a ``FOR KEY SHARE`` lock on the referenced request row, to
    stop the parent disappearing mid-insert. If two transactions each insert their
    donation first and only then ask for ``FOR UPDATE``, each is holding a key-share lock
    the other's exclusive lock must wait for, and PostgreSQL kills one of them with a
    deadlock. Acquiring the exclusive lock first gives every writer the same lock order,
    so the second simply waits for the first to commit.
    """

    request = session.execute(
        sa.select(BloodRequest).where(BloodRequest.id == request_id).with_for_update()
    ).scalar_one_or_none()

    if request is None:
        raise RequestNotFound(f"No blood request with id {request_id}.")

    return request


def recompute_request_fulfilment(session: Session, request_id: int) -> BloodRequest:
    """Recalculate ``units_fulfilled`` and ``status`` for one request.

    The total is recomputed with SUM rather than by incrementing the stored value by the
    units just donated. Incrementing compounds any error that ever gets in, and it is
    wrong the moment a donation is corrected or deleted. Recomputing makes the donations
    table the sole authority and the column a cache that cannot drift.

    The row lock is re-acquired here, which is free when the caller already holds it -
    ``FOR UPDATE`` twice in one transaction is a no-op - and correct when this is called
    on its own, for instance after deleting a donation.
    """

    request = lock_request(session, request_id)

    total: Optional[int] = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Donation.units_given), 0)).where(
            Donation.request_id == request_id
        )
    )

    request.units_fulfilled = int(total or 0)
    request.status = derive_status(request.units_fulfilled, request.units_required)

    # Flushed so that the database check constraint tying status to the unit arithmetic
    # is evaluated here, where the failure points at this function, rather than at some
    # later unrelated commit.
    session.flush()

    return request
