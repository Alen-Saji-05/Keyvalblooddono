"""Network summary schema."""

from __future__ import annotations

from typing import List

from .base import OutModel
from ..models.enums import BloodGroup


class BloodGroupDemandOut(OutModel):
    blood_group: BloodGroup
    open_units_needed: int
    eligible_donors: int


class SummaryOut(OutModel):
    """The four figures the brief asks for, plus the context needed to read them.

    ``scope`` distinguishes the administrator's network-wide view from the patient's view
    of their own requests. The same endpoint serves both, and without the field a client
    could render a patient's three requests under a heading that says network total.
    """

    scope: str

    # "Total number of donations arranged". Reported as both a count of donation events
    # and a sum of units, because they are different numbers and either alone is
    # misleading: forty donations of one unit is not the same operational picture as
    # twenty of two.
    total_donations: int
    total_units_donated: int

    # "Requests fulfilled vs unfulfilled". Unfulfilled is split into never-started and
    # part-met, because a request sitting at three of four units needs one more donor
    # while a request at zero needs a broadcast, and averaging them into one number hides
    # which is which.
    requests_total: int
    requests_fulfilled: int
    requests_partially_fulfilled: int
    requests_open: int
    requests_unfulfilled: int

    # "Donor response rate to broadcasts". The denominator is notifications sent, not
    # donors, so a donor notified about three requests counts three times. That is the
    # right denominator for measuring whether broadcasts work.
    notifications_sent: int
    notifications_responded: int
    donor_response_rate: float

    # "Count of currently registered donors who are eligible to donate right now".
    donors_registered: int
    donors_available: int
    donors_eligible_now: int

    # Present only on the network-wide view.
    demand_by_blood_group: List[BloodGroupDemandOut] = []
