"""JWT issuance, revocation, and the callbacks that wire Flask-JWT-Extended in."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

import sqlalchemy as sa
from flask import Flask
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt

from ..extensions import db, jwt
from ..models import TokenBlocklist, User


def issue_tokens(user: User) -> Tuple[str, str, int]:
    """Mint an access and a refresh token for a user.

    The role and donor link are embedded as claims so that an authorisation decision does
    not require a database round trip on every request. They are a cache of the user row,
    and because the access token lives fifteen minutes, a role change takes at most that
    long to be reflected in the claims. Anything that must take effect immediately -
    deactivating an account - is checked against the database instead, in the user
    lookup callback below.
    """

    from flask import current_app

    claims = {"role": user.role.value, "donor_id": user.donor_id}
    identity = str(user.id)

    access_token = create_access_token(identity=identity, additional_claims=claims)
    refresh_token = create_refresh_token(identity=identity, additional_claims=claims)
    expires_in = int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())

    return access_token, refresh_token, expires_in


def revoke_token(jwt_payload: dict, user_id: int) -> None:
    """Record a token's identifier so it is refused from now on.

    The token's own expiry is stored alongside it, so a periodic job can discard the row
    once the token would have expired anyway rather than the table growing per logout.
    """

    expires_at = datetime.fromtimestamp(jwt_payload["exp"], tz=timezone.utc)
    db.session.add(
        TokenBlocklist(jti=jwt_payload["jti"], user_id=user_id, expires_at=expires_at)
    )


def is_revoked(jti: str) -> bool:
    return (
        db.session.scalar(sa.select(sa.literal(1)).where(TokenBlocklist.jti == jti)) is not None
    )


def current_user_or_none() -> Optional[User]:
    """The authenticated user, or None outside an authenticated request."""

    from flask_jwt_extended import get_current_user

    try:
        return get_current_user()
    except RuntimeError:
        return None


def register_jwt_callbacks(app: Flask) -> None:
    @jwt.user_identity_loader
    def user_identity(identity):
        # The subject claim must be a string. Returning an integer produces a token that
        # some verifiers accept and others reject, which is a difficult failure to chase.
        return str(identity)

    @jwt.user_lookup_loader
    def load_user(_jwt_header, jwt_payload):
        """Load the account behind a token on every authenticated request.

        This is a database query per request, and it is deliberate. Without it, revoking
        an administrator's access would take effect only when their current access token
        expired, leaving up to fifteen minutes during which a deactivated account can
        still read every donor's contact details. Trading one indexed primary key lookup
        for immediate deactivation is the right side of that bargain.

        Returning None makes Flask-JWT-Extended reject the request, so a deleted or
        deactivated account is refused rather than being handed an authenticated context
        with a missing user.
        """

        user = db.session.get(User, int(jwt_payload["sub"]))
        if user is None or not user.is_active:
            return None
        return user

    @jwt.token_in_blocklist_loader
    def check_revoked(_jwt_header, jwt_payload) -> bool:
        """Consult the blocklist, for refresh tokens only.

        Access tokens live fifteen minutes, so checking each one would add a query to
        every authenticated request purely to shorten a window that is already short.
        Refresh tokens live a week, which is long enough that logging out has to actually
        invalidate them.
        """

        if jwt_payload.get("type") != "refresh":
            return False
        return is_revoked(jwt_payload["jti"])

    # The four callbacks below exist so that an authentication failure comes back in the
    # same error envelope as everything else. Flask-JWT-Extended's defaults use their own
    # JSON shape, which would leave the frontend parsing two formats.
    from ..api.errors import error_response

    @jwt.unauthorized_loader
    def missing_token(reason: str):
        return error_response("unauthorised", reason, 401)

    @jwt.invalid_token_loader
    def invalid_token(reason: str):
        return error_response("invalid_token", reason, 401)

    @jwt.expired_token_loader
    def expired_token(_jwt_header, jwt_payload):
        # A distinct code, because this is the one authentication failure the client
        # should respond to by silently refreshing rather than by sending the user to the
        # login screen.
        kind = jwt_payload.get("type", "access")
        return error_response("token_expired", f"The {kind} token has expired.", 401)

    @jwt.revoked_token_loader
    def revoked_token(_jwt_header, _jwt_payload):
        return error_response("token_revoked", "This session has been ended.", 401)

    @jwt.user_lookup_error_loader
    def user_gone(_jwt_header, _jwt_payload):
        return error_response(
            "account_unavailable", "This account is no longer active.", 401
        )


def current_claims() -> dict:
    return get_jwt()
