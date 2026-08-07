"""A single error response shape for the whole API.

Every failure - validation, authorisation, a missing row, a constraint violation, an
unhandled exception - leaves the API as:

    {"error": {"code": "...", "message": "...", "details": {...}}}

The frontend then has one thing to parse. Without this, Flask returns HTML for a 404,
Flask-JWT-Extended returns its own JSON shape for an expired token, Pydantic raises
something else again, and the client ends up with a branch per error source.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from flask import Flask, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An error with a deliberate HTTP status and a machine-readable code."""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details or {}


class NotFound(ApiError):
    status_code = 404
    code = "not_found"


class Unauthorised(ApiError):
    status_code = 401
    code = "unauthorised"


class Forbidden(ApiError):
    status_code = 403
    code = "forbidden"


class Conflict(ApiError):
    status_code = 409
    code = "conflict"


class UnprocessableEntity(ApiError):
    status_code = 422
    code = "validation_error"


def error_response(code: str, message: str, status: int, details: Optional[Dict] = None):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def _format_validation_error(exc: ValidationError) -> Dict[str, Any]:
    """Turn Pydantic's error list into a field-keyed map.

    Pydantic returns a list of errors each carrying a location tuple. A form wants to
    show a message next to a field, so the list is reshaped into
    ``{"field": ["message"]}``. Errors on the model as a whole, which have an empty
    location, are collected under a non-field key rather than being dropped.
    """

    fields: Dict[str, list] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "_"
        fields.setdefault(location, []).append(error["msg"])
    return {"fields": fields}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return error_response(
            "validation_error",
            "The submitted data is not valid.",
            422,
            _format_validation_error(exc),
        )

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(exc: IntegrityError):
        # A constraint violation that reached this handler is a case the service layer
        # did not anticipate. The database message is logged but not returned: it names
        # tables, columns, and constraints, which is more than a client needs to know.
        logger.warning("Unhandled integrity error: %s", exc.orig)
        return error_response(
            "conflict",
            "That change conflicts with data already in the system.",
            409,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        # Catches Flask's own 404, 405, 400 and so on, so they come back as JSON in the
        # same shape rather than as an HTML error page.
        return error_response(
            (exc.name or "error").lower().replace(" ", "_"),
            exc.description or "Request failed.",
            exc.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        # Logged with a traceback, reported without one. An unhandled exception message
        # can carry connection strings, file paths, or row contents.
        logger.exception("Unhandled exception")
        if app.config.get("DEBUG"):
            return error_response("internal_error", f"{type(exc).__name__}: {exc}", 500)
        return error_response("internal_error", "Something went wrong.", 500)
