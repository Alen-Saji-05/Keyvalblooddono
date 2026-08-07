"""Blood requests: creation, scoped listing, and serialisation."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..api.errors import Forbidden, NotFound
from ..models import BloodRequest, Donation, Notification, RequestStatus, User, UserRole
from ..schemas.request import BloodRequestCreateIn, BloodRequestSearchParams


def create_request(
    session: Session, payload: BloodRequestCreateIn, author: User
) -> BloodRequest:
    """File a request.

    The author is taken from the authenticated user, never from the body. Accepting an
    author id from the client would let a patient file a request in someone else's name
    and, worse, would let them attach their own request to another account and read that
    account's requests through the ownership check.
    """

    request = BloodRequest(
        created_by_user_id=author.id,
        patient_name=payload.patient_name,
        blood_group=payload.blood_group,
        hospital=payload.hospital,
        place=payload.place,
        contact_phone=payload.contact_phone,
        units_required=payload.units_required,
        needed_by_date=payload.needed_by_date,
        notes=payload.notes,
        status=RequestStatus.OPEN,
    )
    session.add(request)
    session.flush()
    return request


def _visibility_filter(user: User):
    """Restrict a request query to what this account may see.

    Admins see everything. Patients see only requests they filed. Donors see only requests
    they were notified about, which is the set they have a reason to know exists - a donor
    should not be able to browse every medical need in the network, but they must be able
    to read the appeal they were sent.
    """

    if user.role is UserRole.ADMIN:
        return sa.true()

    if user.role is UserRole.PATIENT:
        return BloodRequest.created_by_user_id == user.id

    if user.role is UserRole.DONOR:
        return BloodRequest.id.in_(
            sa.select(Notification.request_id).where(Notification.donor_id == user.donor_id)
        )

    # Defaulting to nothing rather than everything. If a role is ever added and this
    # function is not updated, the failure is an empty list, not a disclosure.
    return sa.false()


def search_requests(
    session: Session, user: User, params: BloodRequestSearchParams
) -> Tuple[Sequence[BloodRequest], int]:
    conditions = [_visibility_filter(user)]

    if params.status is not None:
        conditions.append(BloodRequest.status == params.status)
    if params.blood_group is not None:
        conditions.append(BloodRequest.blood_group == params.blood_group)
    if params.place:
        conditions.append(
            sa.func.lower(BloodRequest.place).like(f"{params.place.strip().lower()}%")
        )
    if not params.include_expired:
        # A request whose date has passed but which is still short of units stays hidden
        # unless asked for. Fulfilled requests are kept regardless, since they are history
        # rather than outstanding work.
        conditions.append(
            sa.or_(
                BloodRequest.needed_by_date >= date.today(),
                BloodRequest.status == RequestStatus.FULFILLED,
            )
        )

    where = sa.and_(*conditions)

    total = (
        session.scalar(sa.select(sa.func.count()).select_from(BloodRequest).where(where)) or 0
    )

    rows = session.scalars(
        sa.select(BloodRequest)
        .where(where)
        # Soonest deadline first: this list is a work queue, and the request needed
        # tomorrow matters more than the one needed next month regardless of filing order.
        .order_by(BloodRequest.needed_by_date.asc(), BloodRequest.id.desc())
        .limit(params.page_size)
        .offset(params.offset)
    ).all()

    return rows, total


def get_request_for(session: Session, request_id: int, user: User) -> BloodRequest:
    """Load a request the user is permitted to see.

    A permitted-but-absent request and a forbidden one both raise 404. Returning 403 for
    the second would confirm that a request with that id exists, which lets anyone
    enumerate how many requests the network holds and probe for their existence.
    """

    request = session.scalar(
        sa.select(BloodRequest).where(
            BloodRequest.id == request_id, _visibility_filter(user)
        )
    )
    if request is None:
        raise NotFound("No blood request with that id.")
    return request


def require_can_administer(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise Forbidden("Only an administrator can perform this action.")


def _progress_counts(session: Session, request_ids: Sequence[int]) -> Dict[int, Dict[str, int]]:
    """Notification and donation counts for a set of requests.

    Two grouped queries for the whole page rather than per-row counts. Serialising a page
    of twenty five requests with inline counts would issue fifty extra queries, which is
    the classic N+1 and shows up immediately once the request list is more than a demo.
    """

    if not request_ids:
        return {}

    counts: Dict[int, Dict[str, int]] = {
        rid: {"notified": 0, "responded": 0, "donations": 0} for rid in request_ids
    }

    notification_rows = session.execute(
        sa.select(
            Notification.request_id,
            sa.func.count().label("notified"),
            sa.func.count().filter(Notification.responded.is_(True)).label("responded"),
        )
        .where(Notification.request_id.in_(request_ids))
        .group_by(Notification.request_id)
    ).all()
    for row in notification_rows:
        counts[row.request_id]["notified"] = row.notified
        counts[row.request_id]["responded"] = row.responded

    donation_rows = session.execute(
        sa.select(Donation.request_id, sa.func.count().label("donations"))
        .where(Donation.request_id.in_(request_ids))
        .group_by(Donation.request_id)
    ).all()
    for row in donation_rows:
        counts[row.request_id]["donations"] = row.donations

    return counts


def serialise_request(request: BloodRequest, progress: Optional[Dict[str, int]] = None) -> dict:
    progress = progress or {"notified": 0, "responded": 0, "donations": 0}
    return {
        "id": request.id,
        "patient_name": request.patient_name,
        "blood_group": request.blood_group.value,
        "hospital": request.hospital,
        "place": request.place,
        "contact_phone": request.contact_phone,
        "units_required": request.units_required,
        "units_fulfilled": request.units_fulfilled,
        "units_outstanding": request.units_outstanding,
        "needed_by_date": request.needed_by_date.isoformat(),
        "status": request.status.value,
        "notes": request.notes,
        "created_at": request.created_at.isoformat(),
        "created_by_user_id": request.created_by_user_id,
        "notified_count": progress["notified"],
        "responded_count": progress["responded"],
        "donation_count": progress["donations"],
        "is_expired": (
            request.needed_by_date < date.today()
            and request.status is not RequestStatus.FULFILLED
        ),
    }


def serialise_requests(session: Session, requests: Sequence[BloodRequest]) -> List[dict]:
    progress = _progress_counts(session, [r.id for r in requests])
    return [serialise_request(r, progress.get(r.id)) for r in requests]
