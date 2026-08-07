"""Turning a Flask request into a validated Pydantic model."""

from __future__ import annotations

from typing import Any, Type, TypeVar

from flask import request
from pydantic import BaseModel, TypeAdapter

from .errors import ApiError

T = TypeVar("T", bound=BaseModel)


def json_body() -> dict:
    """The request body as a dictionary, with clear errors when it is not one.

    ``silent=True`` is used so that a malformed or absent body produces the messages
    below rather than Flask's generic 400 HTML page.
    """

    if not request.is_json:
        raise ApiError(
            "Expected a JSON request body.",
            status_code=415,
            code="unsupported_media_type",
        )

    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body is missing or is not valid JSON.", status_code=400)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.", status_code=400)

    return data


def parse_body(schema: Type[T] | TypeAdapter, data: dict | None = None) -> Any:
    """Validate the JSON body against a model or a TypeAdapter.

    ``data`` may be supplied by a caller that has already read the body in order to
    choose which schema applies, so the body is not parsed twice.

    A ``ValidationError`` is allowed to propagate: the application-wide handler already
    converts it into a 422 with per-field messages, so catching it here would only mean
    reformatting the same thing twice.
    """

    payload = json_body() if data is None else data

    if isinstance(schema, TypeAdapter):
        return schema.validate_python(payload)
    return schema.model_validate(payload)


def parse_query(schema: Type[T]) -> T:
    """Validate query string parameters against a model.

    ``request.args.to_dict()`` keeps only the first value of a repeated parameter, which
    is what every filter here wants. Any future parameter that genuinely repeats will
    need ``getlist`` instead, and this is the one place that would change.
    """

    return schema.model_validate(request.args.to_dict())
