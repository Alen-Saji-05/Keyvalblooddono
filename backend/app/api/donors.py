"""The donor directory. Administrator only, except for a donor's own record."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..extensions import db
from ..models import UserRole
from ..schemas.common import paginated
from ..schemas.donor import DonorCreateIn, DonorSearchParams, DonorStatusIn, DonorUpdateIn
from ..security.rbac import admin_required, require_own_donor_record, roles_required
from ..services import donors as donor_service
from .parsing import parse_body, parse_query

bp = Blueprint("donors", __name__)


@bp.post("")
@admin_required
def register_donor():
    """Register a donor without creating a login for them.

    Most donors in a network of this kind are signed up at a drive by a member of staff
    and never use the portal. A login can be attached later through the user endpoints if
    they want one.
    """

    payload = parse_body(DonorCreateIn)
    donor = donor_service.create_donor(db.session, payload)
    db.session.commit()
    return jsonify(donor_service.serialise_donor(donor)), 201


@bp.get("")
@admin_required
def list_donors():
    """Search the directory.

    Administrator only. Patients have no workflow reason to see donor identities or
    contact details, because they cannot contact donors directly - broadcasting is an
    administrator action. They get aggregate counts from /api/availability instead.
    """

    params = parse_query(DonorSearchParams)
    rows, total = donor_service.search_donors(db.session, params)
    return jsonify(paginated(donor_service.serialise_donors(rows), total, params))


@bp.get("/<int:donor_id>")
@roles_required(UserRole.ADMIN, UserRole.DONOR)
def get_donor(donor_id: int):
    require_own_donor_record(donor_id)
    donor = donor_service.get_donor(db.session, donor_id)
    return jsonify(donor_service.serialise_donor(donor))


@bp.patch("/<int:donor_id>")
@roles_required(UserRole.ADMIN, UserRole.DONOR)
def update_donor(donor_id: int):
    require_own_donor_record(donor_id)
    payload = parse_body(DonorUpdateIn)
    donor = donor_service.get_donor(db.session, donor_id)
    donor_service.update_donor(db.session, donor, payload)
    db.session.commit()
    return jsonify(donor_service.serialise_donor(donor))


@bp.patch("/<int:donor_id>/status")
@roles_required(UserRole.ADMIN, UserRole.DONOR)
def set_donor_status(donor_id: int):
    """Mark a donor unavailable with a reason, or available again.

    A donor may set their own status, which is the point of giving donors accounts at
    all: the person who knows they are travelling next month is the donor, not the
    administrator who would otherwise have to be told.
    """

    require_own_donor_record(donor_id)
    payload = parse_body(DonorStatusIn)
    donor = donor_service.get_donor(db.session, donor_id)
    donor_service.set_status(db.session, donor, payload)
    db.session.commit()
    return jsonify(donor_service.serialise_donor(donor))
