"""Role-based authorisation, and an audit that no endpoint is unprotected by accident."""

from __future__ import annotations

import pytest

from .conftest import auth_header, make_donor

STRONG_PASSWORD = "a-sufficiently-long-passphrase"

# Endpoints that are deliberately reachable without an access token. Anything not listed
# here must be protected, and the audit test below fails if a new route appears that is
# neither in this list nor decorated with a role requirement. The point is that adding an
# unprotected endpoint has to be a conscious act recorded in this file, rather than
# something that happens by forgetting a decorator.
INTENTIONALLY_PUBLIC = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
}

# Endpoints protected by a refresh token rather than by a role. They carry no role
# decorator because any signed-in account may refresh or sign out.
REFRESH_TOKEN_PROTECTED = {
    "/api/auth/refresh",
    "/api/auth/logout",
}


class TestRouteAudit:
    def test_every_route_is_either_public_by_intent_or_protected(self, app):
        unprotected = []
        for rule in app.url_map.iter_rules():
            path = str(rule)
            if not path.startswith("/api"):
                continue
            if path in INTENTIONALLY_PUBLIC or path in REFRESH_TOKEN_PROTECTED:
                continue
            view = app.view_functions[rule.endpoint]
            if not getattr(view, "__allowed_roles__", None):
                unprotected.append(path)

        assert not unprotected, (
            "These endpoints have no role requirement and are not listed as "
            f"intentionally public: {sorted(unprotected)}"
        )

    def test_protected_endpoints_reject_an_absent_token(self, client, app):
        for rule in app.url_map.iter_rules():
            path = str(rule)
            if not path.startswith("/api") or path in INTENTIONALLY_PUBLIC:
                continue
            if "<" in path:
                continue
            for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                response = client.open(path, method=method)
                assert response.status_code == 401, (
                    f"{method} {path} returned {response.status_code} without a token"
                )


class TestUserManagementIsAdminOnly:
    @pytest.mark.parametrize("fixture_name", ["patient", "donor_account"])
    def test_non_admins_cannot_list_accounts(self, client, request, fixture_name):
        fixture = request.getfixturevalue(fixture_name)
        email = fixture[1].email if isinstance(fixture, tuple) else fixture.email

        response = client.get("/api/users", headers=auth_header(client, email))
        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "forbidden"

    def test_admin_can_list_accounts(self, client, admin):
        response = client.get("/api/users", headers=auth_header(client, "admin@example.org"))
        assert response.status_code == 200
        assert response.get_json()["total"] == 1

    def test_admin_can_create_another_admin(self, client, admin):
        response = client.post(
            "/api/users",
            headers=auth_header(client, "admin@example.org"),
            json={
                "email": "second.admin@example.org",
                "password": STRONG_PASSWORD,
                "full_name": "Second Admin",
                "role": "admin",
            },
        )
        assert response.status_code == 201
        assert response.get_json()["role"] == "admin"

    def test_donor_account_must_reference_an_existing_donor(self, client, admin):
        response = client.post(
            "/api/users",
            headers=auth_header(client, "admin@example.org"),
            json={
                "email": "orphan@example.org",
                "password": STRONG_PASSWORD,
                "full_name": "Orphan",
                "role": "donor",
            },
        )
        assert response.status_code == 422

    def test_donor_account_creation_links_to_the_record(self, client, admin, session):
        donor = make_donor(phone="9900555001", email="linkme@example.org")
        session.add(donor)
        session.commit()

        response = client.post(
            "/api/users",
            headers=auth_header(client, "admin@example.org"),
            json={
                "email": "linked@example.org",
                "password": STRONG_PASSWORD,
                "full_name": "Linked Donor",
                "role": "donor",
                "donor_id": donor.id,
            },
        )
        assert response.status_code == 201
        assert response.get_json()["donor_id"] == donor.id

    def test_one_donor_record_cannot_have_two_accounts(self, client, admin, donor_account):
        donor, _user = donor_account
        response = client.post(
            "/api/users",
            headers=auth_header(client, "admin@example.org"),
            json={
                "email": "second.login@example.org",
                "password": STRONG_PASSWORD,
                "full_name": "Second Login",
                "role": "donor",
                "donor_id": donor.id,
            },
        )
        assert response.status_code == 409


class TestAdminSelfProtection:
    def test_admin_cannot_deactivate_themselves(self, client, admin):
        """Otherwise the last admin can lock the network out of broadcasting."""

        response = client.patch(
            f"/api/users/{admin.id}",
            headers=auth_header(client, "admin@example.org"),
            json={"is_active": False},
        )
        assert response.status_code == 403

    def test_admin_cannot_demote_themselves(self, client, admin):
        response = client.patch(
            f"/api/users/{admin.id}",
            headers=auth_header(client, "admin@example.org"),
            json={"role": "patient"},
        )
        assert response.status_code == 403

    def test_admin_can_deactivate_someone_else(self, client, admin, patient, session):
        response = client.patch(
            f"/api/users/{patient.id}",
            headers=auth_header(client, "admin@example.org"),
            json={"is_active": False},
        )
        assert response.status_code == 200
        assert response.get_json()["is_active"] is False

    def test_donor_account_role_cannot_be_changed(self, client, admin, donor_account):
        _donor, user = donor_account
        response = client.patch(
            f"/api/users/{user.id}",
            headers=auth_header(client, "admin@example.org"),
            json={"role": "patient"},
        )
        assert response.status_code == 403

    def test_nobody_can_be_promoted_into_a_donor_account(self, client, admin, patient):
        response = client.patch(
            f"/api/users/{patient.id}",
            headers=auth_header(client, "admin@example.org"),
            json={"role": "donor"},
        )
        assert response.status_code == 422

    def test_empty_update_is_rejected(self, client, admin, patient):
        response = client.patch(
            f"/api/users/{patient.id}",
            headers=auth_header(client, "admin@example.org"),
            json={},
        )
        assert response.status_code == 422


class TestErrorEnvelope:
    def test_unknown_route_returns_the_standard_json_shape(self, client):
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        assert response.is_json
        assert set(response.get_json()["error"]) >= {"code", "message"}

    def test_non_json_body_is_refused_clearly(self, client):
        response = client.post(
            "/api/auth/login", data="email=x", content_type="application/x-www-form-urlencoded"
        )
        assert response.status_code == 415
        assert response.get_json()["error"]["code"] == "unsupported_media_type"

    def test_unknown_field_is_refused_rather_than_ignored(self, client, patient):
        response = client.post(
            "/api/auth/login",
            json={
                "email": "patient@example.org",
                "password": "whatever-it-is",
                "remember_me_forever": True,
            },
        )
        assert response.status_code == 422
