"""Blood request, broadcast, donation, and notification schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from ..models.enums import BloodGroup, RequestStatus
from .base import ApiModel, OutModel
from .common import PageParams
from .validators import validate_not_past_date, validate_past_date, validate_phone


class BloodRequestCreateIn(ApiModel):
    patient_name: str = Field(min_length=2, max_length=120)
    blood_group: BloodGroup
    hospital: str = Field(min_length=2, max_length=160)
    place: str = Field(min_length=2, max_length=120)
    contact_phone: str = Field(min_length=7, max_length=20)
    # Bounded above as well as below. An unbounded figure lets a mistyped entry create a
    # request that can never be fulfilled and that would broadcast to the entire donor
    # list on the strength of a typo.
    units_required: int = Field(ge=1, le=20)
    needed_by_date: date
    notes: Optional[str] = Field(default=None, max_length=2000)

    _check_phone = field_validator("contact_phone")(validate_phone)
    _check_needed_by = field_validator("needed_by_date")(validate_not_past_date)


class BloodRequestSearchParams(PageParams):
    status: Optional[RequestStatus] = None
    blood_group: Optional[BloodGroup] = None
    place: Optional[str] = Field(default=None, max_length=120)
    # Requests whose date has passed are hidden by default. An operational list that fills
    # up with last month's unmet requests stops being a work queue.
    include_expired: bool = False


class BroadcastIn(ApiModel):
    """Options for a broadcast.

    ``include_compatible`` widens selection from an exact blood group match to the
    transfusion compatibility matrix. It is off by default so the behaviour matches the
    brief exactly and an administrator opts into the wider list knowingly.

    ``place`` narrows to donors in one locality, which is what makes a broadcast useful
    rather than a mass message: a donor three hundred kilometres away cannot help with a
    request needed tomorrow.
    """

    include_compatible: bool = False
    place: Optional[str] = Field(default=None, max_length=120)


class DonationCreateIn(ApiModel):
    donor_id: int = Field(ge=1)
    units_given: int = Field(ge=1, le=10)
    donation_date: date
    notes: Optional[str] = Field(default=None, max_length=2000)

    _check_date = field_validator("donation_date")(validate_past_date)


class NotificationRespondIn(ApiModel):
    """A donor answering a broadcast.

    ``willing=False`` is recorded as a response too. A declined broadcast is still a donor
    who read the message and answered, and counting only the yeses would understate the
    response rate while overstating how many people are simply ignoring notifications.
    """

    willing: bool = True


class DonationOut(OutModel):
    id: int
    donor_id: int
    donor_name: Optional[str] = None
    request_id: int
    units_given: int
    donation_date: date
    notes: Optional[str]
    created_at: datetime


class NotificationOut(OutModel):
    id: int
    donor_id: int
    request_id: int
    sent_at: datetime
    responded: bool
    response_at: Optional[datetime]
    channel: str
    delivery_error: Optional[str] = None


class NotificationInboxOut(OutModel):
    """A donor's view of a broadcast they received.

    Flattens the request into the notification because a donor's inbox is a list of
    appeals, not a list of join rows, and making the client fetch each request separately
    would be a request per row.
    """

    id: int
    request_id: int
    sent_at: datetime
    responded: bool
    response_at: Optional[datetime]

    patient_name: str
    blood_group: BloodGroup
    hospital: str
    place: str
    contact_phone: str
    units_required: int
    units_fulfilled: int
    units_outstanding: int
    needed_by_date: date
    request_status: RequestStatus


class BloodRequestOut(OutModel):
    id: int
    patient_name: str
    blood_group: BloodGroup
    hospital: str
    place: str
    contact_phone: str
    units_required: int
    units_fulfilled: int
    units_outstanding: int
    needed_by_date: date
    status: RequestStatus
    notes: Optional[str]
    created_at: datetime
    created_by_user_id: Optional[int]

    # Outreach progress, so a patient can see that their request is being worked on even
    # before any units arrive. Counts only, never identities.
    notified_count: int = 0
    responded_count: int = 0
    donation_count: int = 0
    is_expired: bool = False


class BroadcastResultOut(OutModel):
    """What a broadcast did.

    Reports the skipped counts, not only the successes. An administrator who broadcasts
    and sees "0 notified" needs to know whether that means there are no eligible donors of
    that group or whether everyone eligible was already notified, because the two call for
    completely different next steps.
    """

    request_id: int
    notified: int
    already_notified: int
    eligible_total: int
    delivery_failures: int
    targeted_blood_groups: List[BloodGroup]
