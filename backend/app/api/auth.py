"""Authentication endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response
from flask_jwt_extended import (
    get_jwt,
    jwt_required,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from ..extensions import db, limiter
from ..models import RevocationReason
from ..schemas.auth import (
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    UserOut,
    registration_model_for,
)
from ..security.rbac import authenticated, current_user
from ..security.tokens import issue_tokens, revoke_token
from ..services import accounts
from .parsing import json_body, parse_body

bp = Blueprint("auth", __name__)


def _authenticated_response(user, status: int = 200):
    """Build the login or refresh response.

    The access token goes in the body for the client to hold in memory. The refresh token
    goes only into an httpOnly cookie, so it is never visible to JavaScript and a script
    that reads the response body still cannot obtain a long-lived credential.
    """

    access_token, refresh_token, expires_in = issue_tokens(user)

    body = LoginOut(
        access_token=access_token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )
    response = make_response(jsonify(body.model_dump(mode="json")), status)
    set_refresh_cookies(response, refresh_token)
    return response


@bp.post("/register")
@limiter.limit("5 per hour")
def register():
    """Create a donor or patient account.

    Public by design: a donation network that needs staff intervention to accept a new
    donor will not grow. The administrator role is unreachable here - the role selects
    which schema validates the body, and no schema exists for admin, so there is no field
    a caller could set to escalate.

    Rate limited per address because this endpoint writes rows and sends nothing that
    would otherwise throttle it.
    """

    data = json_body()
    payload = parse_body(registration_model_for(data.get("role")), data)
    user = accounts.register_account(db.session, payload)
    db.session.commit()
    return _authenticated_response(user, status=201)


@bp.post("/login")
@limiter.limit(lambda: current_app.config["RATELIMIT_LOGIN"])
def login():
    """Exchange credentials for tokens.

    Rate limited: an unthrottled login endpoint on a system with public sign-up is a
    credential-stuffing target, and Argon2 verification is expensive enough that
    unlimited attempts are also a denial-of-service vector.
    """

    payload = parse_body(LoginIn)
    user = accounts.authenticate(db.session, payload.email, payload.password)
    # Committed because authenticate may have rehashed the password to current Argon2
    # parameters and stamps last_login_at.
    db.session.commit()
    return _authenticated_response(user)


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """Exchange a refresh token for a new access token, rotating the refresh token.

    The presented refresh token is revoked and a new one issued, rather than the same
    token being reused for its whole seven day life. Rotation limits the value of a
    stolen refresh token to a single use, and because the old token is blocklisted, a
    thief and the legitimate user cannot both keep refreshing: the second one to present
    the superseded token is rejected, which surfaces the theft instead of hiding it.
    """

    user = current_user()
    revoke_token(get_jwt(), user.id)
    db.session.commit()
    return _authenticated_response(user)


@bp.post("/logout")
@jwt_required(refresh=True)
def logout():
    """End the session.

    Requires the refresh token rather than the access token, because the refresh token is
    the thing that has to be revoked. Revoking only the access token would leave a
    credential valid for another week and make the logout button a lie.
    """

    user = current_user()
    # Revoked as a logout rather than a rotation, so it is refused immediately with no
    # grace period. See RevocationReason.
    revoke_token(get_jwt(), user.id, reason=RevocationReason.LOGOUT)
    db.session.commit()

    response = make_response(jsonify({"status": "signed out"}), 200)
    unset_jwt_cookies(response)
    return response


@bp.get("/me")
@authenticated
def me():
    """The signed-in account.

    Called by the frontend on load to restore a session: the access token is held in
    memory and lost on refresh, so the client silently refreshes and then asks who it is.
    """

    return jsonify(UserOut.model_validate(current_user()).model_dump(mode="json"))


@bp.patch("/me/password")
@authenticated
def change_own_password():
    """Change the signed-in account's password.

    Every other session is left alone deliberately. Revoking them all is defensible, but
    it would sign the user out of their phone because they changed a password on a
    laptop, and this system has no way to tell them why.
    """

    payload = parse_body(PasswordChangeIn)
    user = current_user()
    accounts.change_password(db.session, user, payload.current_password, payload.new_password)
    db.session.commit()
    return jsonify({"status": "password changed"})
