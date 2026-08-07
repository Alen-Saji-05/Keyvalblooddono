"""Donor registry: search, registration, edits, and availability."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..api.errors import Conflict, NotFound
from ..models import Donor, DonorStatus
from ..schemas.donor import DonorCreateIn, DonorSearchParams, DonorStatusIn, DonorUpdateIn
from .eligibility import (
    EligibilityRules,
    calculate_age,
    eligibility_clause,
    ineligibility_reasons,
    next_eligible_date,
)


def get_donor(session: Session, donor_id: int) -> Donor:
    donor = session.get(Donor, donor_id)
    if donor is None:
        raise NotFound("No donor with that id.")
    return donor


def _place_filter(place: str):
    """Case-insensitive prefix match on place.

    A prefix rather than a substring match, because the index is on ``lower(place)`` and a
    btree can serve ``lower(place) LIKE 'kochi%'`` but not ``LIKE '%kochi%'``. A leading
    wildcard would force a sequential scan of the entire donor table on every filtered
    search. Substring search across a donor's details is available separately through the
    ``q`` parameter, which is used far less often.
    """

    return sa.func.lower(Donor.place).like(f"{place.strip().lower()}%")


def search_donors(
    session: Session, params: DonorSearchParams
) -> Tuple[Sequence[Donor], int]:
    """Filter the donor directory, returning one page and the unpaged total."""

    conditions = []

    if params.blood_group is not None:
        conditions.append(Donor.blood_group == params.blood_group)
    if params.status is not None:
        conditions.append(Donor.status == params.status)
    if params.place:
        conditions.append(_place_filter(params.place))
    if params.eligible_only:
        # The same predicate the broadcast selector uses, so what a coordinator sees when
        # filtering for eligible donors is exactly who a broadcast would reach.
        conditions.append(eligibility_clause())
    if params.q:
        term = f"%{params.q.strip().lower()}%"
        conditions.append(
            sa.or_(
                sa.func.lower(Donor.name).like(term),
                sa.func.lower(Donor.place).like(term),
                Donor.phone.like(term),
                sa.func.lower(sa.func.coalesce(Donor.email, "")).like(term),
            )
        )

    where = sa.and_(*conditions) if conditions else sa.true()

    total = session.scalar(sa.select(sa.func.count()).select_from(Donor).where(where)) or 0

    rows = session.scalars(
        sa.select(Donor)
        .where(where)
        # Newest first, then id, so that two donors registered in the same second do not
        # swap places between pages and cause one to be shown twice and another skipped.
        .order_by(Donor.created_at.desc(), Donor.id.desc())
        .limit(params.page_size)
        .offset(params.offset)
    ).all()

    return rows, total


def create_donor(session: Session, payload: DonorCreateIn) -> Donor:
    existing = session.scalar(sa.select(Donor).where(Donor.phone == payload.phone))
    if existing is not None:
        raise Conflict("A donor is already registered with that phone number.")

    email = payload.email.strip().lower() if payload.email else None
    if email:
        clash = session.scalar(sa.select(Donor).where(sa.func.lower(Donor.email) == email))
        if clash is not None:
            raise Conflict("A donor is already registered with that email address.")

    donor = Donor(
        name=payload.name,
        blood_group=payload.blood_group,
        sex=payload.sex,
        date_of_birth=payload.date_of_birth,
        weight_kg=payload.weight_kg,
        phone=payload.phone,
        email=email,
        place=payload.place,
        last_donation_date=payload.last_donation_date,
        status=DonorStatus.AVAILABLE,
    )
    session.add(donor)
    session.flush()
    return donor


def update_donor(session: Session, donor: Donor, payload: DonorUpdateIn) -> Donor:
    changes = payload.model_dump(exclude_unset=True)

    if "phone" in changes:
        clash = session.scalar(
            sa.select(Donor).where(Donor.phone == changes["phone"], Donor.id != donor.id)
        )
        if clash is not None:
            raise Conflict("Another donor is registered with that phone number.")

    if "email" in changes and changes["email"]:
        changes["email"] = changes["email"].strip().lower()
        clash = session.scalar(
            sa.select(Donor).where(
                sa.func.lower(Donor.email) == changes["email"], Donor.id != donor.id
            )
        )
        if clash is not None:
            raise Conflict("Another donor is registered with that email address.")

    for field, value in changes.items():
        setattr(donor, field, value)

    session.flush()
    return donor


def set_status(session: Session, donor: Donor, payload: DonorStatusIn) -> Donor:
    """Mark a donor available or unavailable.

    Returning to available clears the note. Leaving a stale explanation attached to an
    available donor would show a coordinator "moved away" next to somebody who is standing
    by to give.
    """

    donor.status = payload.status
    donor.status_note = None if payload.status is DonorStatus.AVAILABLE else payload.note
    session.flush()
    return donor


def serialise_donor(donor: Donor, rules: Optional[EligibilityRules] = None) -> dict:
    """Build the donor response, with eligibility computed server side.

    ``rules`` is passed in when serialising a list so the configuration is read once for
    the page rather than once per donor.
    """

    rules = rules or EligibilityRules.from_config()
    reasons = ineligibility_reasons(donor, rules)

    return {
        "id": donor.id,
        "name": donor.name,
        "blood_group": donor.blood_group.value,
        "sex": donor.sex.value,
        "date_of_birth": donor.date_of_birth.isoformat(),
        "age": calculate_age(donor.date_of_birth),
        "weight_kg": str(donor.weight_kg),
        "phone": donor.phone,
        "email": donor.email,
        "place": donor.place,
        "last_donation_date": (
            donor.last_donation_date.isoformat() if donor.last_donation_date else None
        ),
        "status": donor.status.value,
        "status_note": donor.status_note,
        "is_eligible": not reasons,
        "ineligibility_reasons": reasons,
        "next_eligible_date": (
            d.isoformat() if (d := next_eligible_date(donor, rules)) else None
        ),
        "created_at": donor.created_at.isoformat(),
    }


def serialise_donors(donors: Sequence[Donor]) -> List[dict]:
    rules = EligibilityRules.from_config()
    return [serialise_donor(donor, rules) for donor in donors]


def availability_by_blood_group(session: Session, place: Optional[str] = None) -> List[dict]:
    """Eligible and total donor counts per blood group.

    This is the view a patient gets in place of the donor directory. It answers whether a
    request has any prospect of being met without disclosing a single identity.

    Computed as one grouped query rather than eight counts, and it deliberately reports a
    row for every blood group including those with no donors at all - a zero is the most
    important number here, and omitting the row would render as absence of data rather
    than absence of donors.
    """

    from ..models.enums import BloodGroup

    conditions = [_place_filter(place)] if place else []
    base = sa.and_(*conditions) if conditions else sa.true()

    rows = session.execute(
        sa.select(
            Donor.blood_group,
            sa.func.count().label("total"),
            sa.func.count().filter(eligibility_clause()).label("eligible"),
        )
        .where(base)
        .group_by(Donor.blood_group)
    ).all()

    counts = {row.blood_group: (row.eligible, row.total) for row in rows}

    return [
        {
            "blood_group": group.value,
            "eligible_donors": counts.get(group, (0, 0))[0],
            "total_donors": counts.get(group, (0, 0))[1],
        }
        for group in BloodGroup
    ]
