"""Schemas for administrator management of accounts."""

from __future__ import annotations

from typing import List, Optional

from pydantic import EmailStr, Field, model_validator

from ..models.enums import UserRole
from .base import ApiModel, OutModel
from .auth import UserOut


class AdminUserCreateIn(ApiModel):
    """An account created by an administrator.

    An admin may create any role, including another admin, which is how administration
    is delegated without anyone touching the CLI again.

    A donor account must name an existing donor record. Admins register donors through
    the donor endpoints, so the record exists first and this only attaches a login to it.
    Accepting a whole donor profile here as well would give the system two different ways
    to create a donor and two places for that logic to diverge.
    """

    email: EmailStr
    password: str
    full_name: str = Field(min_length=2, max_length=120)
    role: UserRole
    donor_id: Optional[int] = None

    @model_validator(mode="after")
    def _check_donor_link(self) -> "AdminUserCreateIn":
        if self.role is UserRole.DONOR and self.donor_id is None:
            raise ValueError("A donor account must reference an existing donor record.")
        if self.role is not UserRole.DONOR and self.donor_id is not None:
            raise ValueError("Only a donor account can reference a donor record.")
        return self


class AdminUserUpdateIn(ApiModel):
    """Changes an administrator may make to an existing account.

    ``role`` may move between admin and patient. It may not move into or out of donor,
    because a donor account is tied to a donor record: promoting a donor would orphan
    their record, and demoting an admin into a donor would need a record that does not
    exist. Those cases are handled by creating the correct account, not by mutating one.

    Deactivation rather than deletion, so that requests a person filed and donations they
    recorded keep their author.
    """

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def _reject_donor_role_change(self) -> "AdminUserUpdateIn":
        if self.role is UserRole.DONOR:
            raise ValueError(
                "An account cannot be changed into a donor account. Create a donor "
                "account against the donor record instead."
            )
        return self

    @model_validator(mode="after")
    def _require_at_least_one_change(self) -> "AdminUserUpdateIn":
        if self.full_name is None and self.role is None and self.is_active is None:
            raise ValueError("Provide at least one field to change.")
        return self


class UserListOut(OutModel):
    items: List[UserOut]
    total: int
