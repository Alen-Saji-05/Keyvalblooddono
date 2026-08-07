"""Reference data and the aggregate availability view."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models.enums import BloodGroup, DonorStatus, RequestStatus, Sex, UserRole
from ..security.rbac import authenticated
from ..services import donors as donor_service
from ..services.compatibility import COMPATIBLE_DONORS

bp = Blueprint("meta", __name__)

# Human-readable labels live on the server rather than being duplicated in the frontend.
# An enum value and the words shown next to it would otherwise drift, and adding a status
# would mean remembering to edit a file in the other half of the codebase.
DONOR_STATUS_LABELS = {
    DonorStatus.AVAILABLE: "Available",
    DonorStatus.UNAVAILABLE_MOVED: "Unavailable - moved away",
    DonorStatus.UNAVAILABLE_TRAVELING: "Unavailable - travelling",
    DonorStatus.UNAVAILABLE_MEDICAL: "Unavailable - medically unable",
}

REQUEST_STATUS_LABELS = {
    RequestStatus.OPEN: "Open",
    RequestStatus.PARTIALLY_FULFILLED: "Partially fulfilled",
    RequestStatus.FULFILLED: "Fulfilled",
}

SEX_LABELS = {Sex.MALE: "Male", Sex.FEMALE: "Female", Sex.OTHER: "Other"}


@bp.get("/meta")
def get_meta():
    """Enumerations and reference data for building forms.

    Public, and deliberately so. It contains no data about any person - only the fixed
    vocabulary of the system, which the login and registration screens need before anyone
    is authenticated.
    """

    from flask import current_app

    cfg = current_app.config

    return jsonify(
        {
            "blood_groups": [g.value for g in BloodGroup],
            "sexes": [{"value": s.value, "label": SEX_LABELS[s]} for s in Sex],
            "donor_statuses": [
                {"value": s.value, "label": DONOR_STATUS_LABELS[s]} for s in DonorStatus
            ],
            "request_statuses": [
                {"value": s.value, "label": REQUEST_STATUS_LABELS[s]} for s in RequestStatus
            ],
            "roles": [r.value for r in UserRole],
            "compatibility": {
                recipient.value: sorted(d.value for d in donors)
                for recipient, donors in COMPATIBLE_DONORS.items()
            },
            "eligibility_rules": {
                "cooldown_days_male": cfg["COOLDOWN_DAYS_MALE"],
                "cooldown_days_female": cfg["COOLDOWN_DAYS_FEMALE"],
                "min_age": cfg["MIN_DONOR_AGE"],
                "max_age": cfg["MAX_DONOR_AGE"],
                "min_weight_kg": cfg["MIN_DONOR_WEIGHT_KG"],
            },
        }
    )


@bp.get("/availability")
@authenticated
def availability():
    """Eligible donor counts by blood group, optionally narrowed to a place.

    This is what a patient sees in place of the donor directory. It answers whether there
    is any prospect of a request being met without disclosing a single identity, which is
    the entire reason the directory itself is restricted.
    """

    place = request.args.get("place")
    return jsonify({"items": donor_service.availability_by_blood_group(db.session, place)})
