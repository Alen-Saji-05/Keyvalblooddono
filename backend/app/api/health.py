"""Liveness and readiness endpoint."""

from __future__ import annotations

import sqlalchemy as sa
from flask import Blueprint, jsonify

from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Report whether the process is up and whether the database answers.

    The database is actually queried rather than assumed reachable. A health check that
    only proves the web process is running will report healthy while every request that
    touches data fails.
    """

    database_ok = True
    try:
        db.session.execute(sa.text("SELECT 1"))
    except Exception:  # noqa: BLE001 - the specific driver error is not useful here
        database_ok = False

    status_code = 200 if database_ok else 503
    return jsonify({"status": "ok" if database_ok else "degraded", "database": database_ok}), (
        status_code
    )
