"""Blood requests, broadcasting, and donation recording."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..extensions import db
from ..models import UserRole
from ..schemas.common import paginated
from ..schemas.request import (
    BloodRequestCreateIn,
    BloodRequestSearchParams,
    BroadcastIn,
    DonationCreateIn,
)
from ..security.rbac import admin_required, authenticated, current_user, roles_required
from ..services import broadcast as broadcast_service
from ..services import donations as donation_service
from ..services import notifications as notification_service
from ..services import requests as request_service
from .parsing import json_body, parse_body, parse_query

bp = Blueprint("requests", __name__)


@bp.post("")
@roles_required(UserRole.PATIENT, UserRole.ADMIN)
def create_request():
    """File a blood request.

    Donors cannot file requests. A donor who needs blood registers as a patient; conflating
    the two would mean a donor account could broadcast to itself.
    """

    payload = parse_body(BloodRequestCreateIn)
    request_row = request_service.create_request(db.session, payload, current_user())
    db.session.commit()
    return jsonify(request_service.serialise_request(request_row)), 201


@bp.get("")
@authenticated
def list_requests():
    """List requests, scoped to what the caller may see.

    Admins see everything, patients see their own, donors see the ones they were notified
    about. The scoping is a SQL filter rather than a post-fetch check, so a request the
    caller may not see is never loaded and cannot leak through a count or a pagination
    total.
    """

    params = parse_query(BloodRequestSearchParams)
    user = current_user()
    rows, total = request_service.search_requests(db.session, user, params)
    return jsonify(paginated(request_service.serialise_requests(db.session, rows), total, params))


@bp.get("/<int:request_id>")
@authenticated
def get_request(request_id: int):
    user = current_user()
    request_row = request_service.get_request_for(db.session, request_id, user)

    body = request_service.serialise_requests(db.session, [request_row])[0]

    # Donor identities on the donation list are for administrators only. A patient sees
    # that three people gave two units on given dates, which is the progress they need,
    # without the names of donors who never agreed to be identified to them.
    body["donations"] = donation_service.list_donations_for_request(
        db.session, request_id, include_donor_names=user.role is UserRole.ADMIN
    )

    if user.role is UserRole.ADMIN:
        body["notifications"] = notification_service.list_for_request(db.session, request_id)

    return jsonify(body)


@bp.post("/<int:request_id>/broadcast")
@admin_required
def broadcast(request_id: int):
    """Notify eligible donors about this request.

    Administrator only. Broadcasting sends real messages to real people, so an unreviewed
    account cannot turn the donor list into a spam surface.

    The body is optional: a bare POST broadcasts to every eligible donor of the exact
    blood group, which is the behaviour the brief describes.
    """

    from flask import request as flask_request

    options = (
        parse_body(BroadcastIn, json_body())
        if flask_request.is_json and flask_request.get_data()
        else BroadcastIn()
    )

    user = current_user()
    request_row = request_service.get_request_for(db.session, request_id, user)
    result = broadcast_service.broadcast_request(db.session, request_row, options)
    db.session.commit()
    return jsonify(result)


@bp.post("/<int:request_id>/donations")
@admin_required
def record_donation(request_id: int):
    """Record a donation against this request and recompute fulfilment.

    Administrator only. These rows are what every fulfilment figure and every analytic is
    computed from, so the beneficiary of a request does not get to write them.

    A request stays open or partially fulfilled until the cumulative units across all
    donations reach what was asked for, which is the normal case: one donor gives roughly
    one unit, so a request for four units needs four people.
    """

    payload = parse_body(DonationCreateIn)
    user = current_user()
    request_row = request_service.get_request_for(db.session, request_id, user)

    donation_service.record_donation(db.session, request_row, payload, user)
    db.session.commit()

    body = request_service.serialise_requests(db.session, [request_row])[0]
    body["donations"] = donation_service.list_donations_for_request(
        db.session, request_id, include_donor_names=True
    )
    return jsonify(body), 201
