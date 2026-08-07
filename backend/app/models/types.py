"""Reusable column types."""

from __future__ import annotations

import enum
from typing import Type

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


def pg_enum(enum_cls: Type[enum.Enum], name: str) -> sa.Enum:
    """Build a native PostgreSQL enum type that stores member *values*.

    SQLAlchemy stores enum *names* by default, which would put ``A_POSITIVE`` in the
    database where ``A+`` belongs. ``values_callable`` overrides that so the stored
    value is the one the API and the frontend already speak, making the table readable
    in a SQL client and removing a translation step at every boundary.

    ``create_type=False`` leaves type creation to the Alembic revision. Letting each
    table definition create the type implicitly causes duplicate-type errors as soon as
    two tables reference the same enum.
    """

    return ENUM(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        create_type=False,
    )
