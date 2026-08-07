"""Enumerations shared by the models, the schemas, and the frontend.

Every enumeration here is persisted as a native PostgreSQL enum type rather than a
free-text column. The database then rejects an invalid value outright instead of
storing it and letting it surface later as a filter that silently matches nothing.

The members inherit from ``str`` so that a value serialises directly to JSON and
compares equal to its wire representation without an explicit ``.value``.
"""

from __future__ import annotations

import enum


class BloodGroup(str, enum.Enum):
    """The eight ABO/Rh whole blood groups."""

    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"


class Sex(str, enum.Enum):
    """Donor sex, recorded because the whole blood inter-donation interval differs.

    ``OTHER`` exists so that a donor is never forced into an inaccurate answer. It is
    treated as the longer of the two intervals when eligibility is computed, because
    erring towards a longer wait is the safe direction for the donor.
    """

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class DonorStatus(str, enum.Enum):
    """Availability, with the reason encoded in the status itself.

    The brief asks for a donor to be marked unavailable with one of three reasons.
    Encoding the reason in the status rather than in a separate nullable column makes
    the invalid combination - unavailable with no reason, or available with one -
    unrepresentable.
    """

    AVAILABLE = "available"
    UNAVAILABLE_MOVED = "unavailable_moved"
    UNAVAILABLE_TRAVELING = "unavailable_traveling"
    UNAVAILABLE_MEDICAL = "unavailable_medical"

    @property
    def is_available(self) -> bool:
        return self is DonorStatus.AVAILABLE


class RequestStatus(str, enum.Enum):
    """Fulfilment state of a blood request.

    ``PARTIALLY_FULFILLED`` exists because a request for several units is normally met
    by several different donors. It is never set by a caller; it is derived from the
    sum of recorded donations. See ``services.fulfilment``.
    """

    OPEN = "open"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"


class UserRole(str, enum.Enum):
    """Who is using the system.

    ``ADMIN`` operates the network: manages donors, broadcasts requests, and records
    donations. ``DONOR`` is a person who gives blood and is linked to a donor record.
    ``PATIENT`` is a person who needs blood and can file requests.
    """

    ADMIN = "admin"
    DONOR = "donor"
    PATIENT = "patient"


class NotificationChannel(str, enum.Enum):
    """Which delivery driver handled a notification.

    Recorded per notification rather than read from configuration at display time, so
    that changing the configured driver later does not rewrite the history of how past
    broadcasts were actually delivered.
    """

    CONSOLE = "console"
    EMAIL = "email"
