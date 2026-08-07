"""Declarative base and shared column mixins."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy 2.0 declarative base.

    Naming conventions are declared here so that Alembic emits stable, predictable
    constraint names. Without them PostgreSQL invents names for unnamed constraints,
    and a later migration that needs to drop one cannot refer to it portably.
    """

    metadata = sa.MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def utc_now_column() -> sa.TextClause:
    """Server-side default for timestamp columns.

    Deliberately a server default rather than a Python default: the database clock is
    the single authority for when a row was written, which keeps timestamps consistent
    even if application processes disagree about the time or run in different zones.
    """

    return sa.text("now()")


class TimestampMixin:
    """Adds creation and modification timestamps.

    Both columns are timezone-aware. Storing naive timestamps would make every value
    ambiguous the moment the application is deployed anywhere other than the machine
    that wrote it.
    """

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=utc_now_column(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=utc_now_column(),
        onupdate=sa.func.now(),
    )
