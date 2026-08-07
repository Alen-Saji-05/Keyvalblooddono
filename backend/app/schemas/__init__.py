"""Pydantic schemas for the HTTP boundary.

Input and output models are kept strictly separate. An input model describes what a
client may send; an output model describes what the API returns. Reusing one model for
both is how a field such as ``password_hash`` ends up in a response by accident, and how
a client discovers it can set a field the endpoint never intended to expose.
"""

from .auth import (
    DonorRegistrationIn,
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    PatientRegistrationIn,
    UserOut,
    registration_model_for,
)
from .base import ApiModel, OutModel
from .user import AdminUserCreateIn, AdminUserUpdateIn, UserListOut

__all__ = [
    "AdminUserCreateIn",
    "AdminUserUpdateIn",
    "ApiModel",
    "DonorRegistrationIn",
    "LoginIn",
    "LoginOut",
    "OutModel",
    "PasswordChangeIn",
    "PatientRegistrationIn",
    "UserListOut",
    "UserOut",
    "registration_model_for",
]
