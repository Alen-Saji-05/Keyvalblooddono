"""Authentication accounts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import RevocationReason, UserRole
from .types import pg_enum

if TYPE_CHECKING:
    from .blood_request import BloodRequest
    from .donor import Donor


class User(Base, TimestampMixin):
    """A login account.

    Accounts are kept separate from donor records rather than adding credentials to the
    donors table. Most donors in a network of this kind are registered by staff and
    never log in, and patients and administrators have no donor record at all, so
    merging the two would leave a table where the majority of the authentication
    columns are null and the meaning of a row depends on which ones are filled.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    # Stored lower-cased by the service layer. Addresses are treated case-insensitively
    # for login, and normalising on write is cheaper and less error-prone than
    # remembering to fold case at every comparison.
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)

    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)

    # Deactivation rather than deletion. A deleted account would take its authored blood
    # requests with it or leave them orphaned, and there is an audit interest in knowing
    # who filed a request even after they stop using the system.
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    donor_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        sa.ForeignKey("donors.id", ondelete="CASCADE", name="fk_users_donor_id_donors"),
        nullable=True,
        unique=True,
    )

    donor: Mapped[Optional["Donor"]] = relationship(back_populates="user")
    requests: Mapped[List["BloodRequest"]] = relationship(back_populates="created_by")

    __table_args__ = (
        # The link to a donor record is meaningful only for the donor role, and is
        # mandatory for it. Enforcing that here means no application path can produce a
        # donor account with nothing to manage, or an admin account that accidentally
        # owns somebody's donation history.
        sa.CheckConstraint(
            "(role = 'donor' AND donor_id IS NOT NULL) "
            "OR (role <> 'donor' AND donor_id IS NULL)",
            name="donor_role_requires_donor_link",
        ),
        sa.Index("ix_users_role", "role"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"


class TokenBlocklist(Base):
    """Refresh tokens that have been revoked.

    Only refresh tokens are recorded. Access tokens live for fifteen minutes, so
    checking each one against this table would add a query to every authenticated
    request in order to shorten an already short window. Refresh tokens live for a week,
    which is long enough that logging out has to actually invalidate them.
    """

    __tablename__ = "token_blocklist"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    # Unique, but deliberately not also index=True. PostgreSQL implements a unique
    # constraint with a unique index, so the lookup on every token refresh is already
    # served; adding a second index would duplicate the same structure.
    jti: Mapped[str] = mapped_column(sa.String(36), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_token_blocklist_user_id_users"),
        nullable=False,
    )
    revoked_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )
    # Rotation and logout are treated differently on reuse. See RevocationReason.
    reason: Mapped[RevocationReason] = mapped_column(
        pg_enum(RevocationReason, "revocation_reason"),
        nullable=False,
        server_default=RevocationReason.ROTATED.value,
    )
    # Rows are only useful until the token they revoke would have expired anyway. This
    # column lets a periodic job discard them instead of the table growing without limit.
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (sa.Index("ix_token_blocklist_expires_at", "expires_at"),)

    def __repr__(self) -> str:
        return f"<TokenBlocklist jti={self.jti!r}>"
