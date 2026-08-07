"""SQLAlchemy models.

Every model is imported here so that a single ``import app.models`` populates
``Base.metadata``. Alembic autogeneration compares the live database against that
metadata, so a model that is never imported is a model Alembic believes does not exist.
"""

from .base import Base
from .blood_request import BloodRequest
from .donation import Donation
from .donor import Donor
from .enums import (
    BloodGroup,
    DonorStatus,
    NotificationChannel,
    RequestStatus,
    RevocationReason,
    Sex,
    UserRole,
)
from .notification import Notification
from .user import TokenBlocklist, User

__all__ = [
    "Base",
    "BloodGroup",
    "BloodRequest",
    "Donation",
    "Donor",
    "DonorStatus",
    "Notification",
    "NotificationChannel",
    "RequestStatus",
    "RevocationReason",
    "Sex",
    "TokenBlocklist",
    "User",
    "UserRole",
]
