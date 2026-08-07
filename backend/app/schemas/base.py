"""Shared Pydantic configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Base for request bodies.

    ``extra="forbid"`` rejects unknown keys rather than ignoring them. A misspelled field
    name would otherwise be silently dropped and the request would appear to succeed
    while doing something other than what the caller asked for. It also stops a client
    from posting a field the endpoint was never meant to accept and having it quietly
    disappear rather than being refused.

    ``str_strip_whitespace`` because trailing spaces in a name or a phone number are
    always a typing artefact, and they defeat uniqueness checks and exact-match filters.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class OutModel(BaseModel):
    """Base for responses built from ORM objects.

    ``from_attributes`` lets a model be constructed straight from a SQLAlchemy instance.
    Output models are kept separate from input models throughout, so that a field such as
    ``password_hash`` is not merely omitted by convention but has no route to a response
    at all.
    """

    model_config = ConfigDict(from_attributes=True)
