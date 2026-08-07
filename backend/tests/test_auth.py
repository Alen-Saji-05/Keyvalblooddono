"""Registration, login, token lifecycle, and password changes."""

from __future__ import annotations

from datetime import date, timedelta

import sqlalchemy as sa

from app.models import Donor, User, UserRole

from .conftest import TEST_PASSWORD, auth_header, login

VALID_PASSWORD = "a-sufficiently-long-passphrase"


def donor_payload(**overrides) -> dict:
    payload = {
        "role": "donor",
        "email": "new.donor@example.org",
        "password": VALID_PASSWORD,
        "full_name": "New Donor",
        "blood_group": "A+",
        "sex": "female",
        "date_of_birth": (date.today() - timedelta(days=28 * 365)).isoformat(),
        "weight_kg": "58.5",
        "phone": "9911223344",
        "place": "Kochi",
    }
    payload.update(overrides)
    return payload


class TestRegistration:
    def test_patient_registration_returns_token_and_user(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "role": "patient",
                "email": "New.Patient@Example.org",
                "password": VALID_PASSWORD,
                "full_name": "New Patient",
            },
        )
        assert response.status_code == 201, response.get_json()
        body = response.get_json()

        assert body["user"]["role"] == "patient"
        # Normalised on write, so the address cannot be registered twice in different
        # cases and login is not case sensitive.
        assert body["user"]["email"] == "new.patient@example.org"
        assert body["user"]["donor_id"] is None
        assert body["access_token"]
        assert "password" not in str(body)

    def test_donor_registration_creates_linked_donor_record(self, client, session):
        response = client.post("/api/auth/register", json=donor_payload())
        assert response.status_code == 201, response.get_json()

        user = session.scalar(sa.select(User).where(User.email == "new.donor@example.org"))
        assert user.role is UserRole.DONOR
        assert user.donor_id is not None

        donor = session.get(Donor, user.donor_id)
        assert donor.blood_group.value == "A+"
        assert donor.phone == "9911223344"
        # The account and the record are created together, so a donor cannot end up
        # logged in with nothing to manage.
        assert donor.email == "new.donor@example.org"

    def test_cannot_self_register_as_admin(self, client, session):
        response = client.post(
            "/api/auth/register",
            json={
                "role": "admin",
                "email": "sneaky@example.org",
                "password": VALID_PASSWORD,
                "full_name": "Sneaky",
            },
        )
        assert response.status_code == 422
        assert session.scalar(sa.select(sa.func.count()).select_from(User)) == 0

    def test_donor_fields_on_a_patient_registration_are_refused_not_ignored(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "role": "patient",
                "email": "p@example.org",
                "password": VALID_PASSWORD,
                "full_name": "P",
                "blood_group": "O+",
            },
        )
        assert response.status_code == 422

    def test_short_password_rejected(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "role": "patient",
                "email": "p@example.org",
                "password": "short",
                "full_name": "Pat Patient",
            },
        )
        assert response.status_code == 422
        # Keyed by the field name alone, with no union-variant prefix, so a form can
        # attach the message to the input it belongs to.
        assert "password" in response.get_json()["error"]["details"]["fields"]

    def test_validation_errors_are_keyed_by_plain_field_name(self, client):
        response = client.post(
            "/api/auth/register",
            json={"role": "donor", "email": "not-an-email", "password": VALID_PASSWORD},
        )
        assert response.status_code == 422
        fields = response.get_json()["error"]["details"]["fields"]
        assert "email" in fields
        assert not any("." in key for key in fields), fields

    def test_password_containing_email_rejected(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "role": "patient",
                "email": "meredith@example.org",
                "password": "meredith-and-more",
                "full_name": "Meredith",
            },
        )
        assert response.status_code == 422

    def test_duplicate_email_conflicts(self, client, patient):
        response = client.post(
            "/api/auth/register",
            json={
                "role": "patient",
                "email": "patient@example.org",
                "password": VALID_PASSWORD,
                "full_name": "Impostor",
            },
        )
        assert response.status_code == 409

    def test_duplicate_donor_phone_conflicts(self, client, donor_account):
        donor, _user = donor_account
        response = client.post(
            "/api/auth/register", json=donor_payload(phone=donor.phone)
        )
        assert response.status_code == 409

    def test_underweight_donor_is_registered_not_refused(self, client, session):
        """Eligibility inputs gate broadcasts, not sign-up."""

        response = client.post("/api/auth/register", json=donor_payload(weight_kg="40.0"))
        assert response.status_code == 201
        assert session.scalar(sa.select(sa.func.count()).select_from(Donor)) == 1

    def test_future_date_of_birth_rejected(self, client):
        future = (date.today() + timedelta(days=1)).isoformat()
        response = client.post("/api/auth/register", json=donor_payload(date_of_birth=future))
        assert response.status_code == 422


class TestLogin:
    def test_login_returns_access_token_and_sets_refresh_cookie(self, client, patient):
        response = login(client, "patient@example.org")
        assert response.status_code == 200

        body = response.get_json()
        assert body["access_token"]
        assert body["expires_in"] == 900
        assert body["user"]["email"] == "patient@example.org"

        # The refresh token must never appear in the body: the whole point of the split
        # is that a script able to read this response still cannot obtain a long-lived
        # credential.
        assert "refresh_token" not in body

        cookies = response.headers.getlist("Set-Cookie")
        refresh_cookie = next(c for c in cookies if "bloodnet_refresh" in c)
        assert "HttpOnly" in refresh_cookie
        # Scoped to the auth namespace: narrow enough that donor, request, and summary
        # traffic never carries this credential, broad enough that logout receives it and
        # can revoke it.
        assert "Path=/api/auth;" in refresh_cookie
        assert "SameSite=Strict" in refresh_cookie

    def test_login_is_case_insensitive_on_email(self, client, patient):
        assert login(client, "PATIENT@EXAMPLE.ORG").status_code == 200

    def test_wrong_password_and_unknown_account_are_indistinguishable(self, client, patient):
        wrong = client.post(
            "/api/auth/login",
            json={"email": "patient@example.org", "password": "not-the-password"},
        )
        unknown = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.org", "password": "not-the-password"},
        )
        assert wrong.status_code == unknown.status_code == 401
        # Identical responses, so the endpoint cannot be used to test whether a given
        # person is registered with this network.
        assert wrong.get_json() == unknown.get_json()

    def test_deactivated_account_cannot_log_in(self, client, session, patient):
        patient.is_active = False
        session.commit()
        response = login(client, "patient@example.org")
        assert response.status_code == 401

    def test_last_login_is_recorded(self, client, session, patient):
        assert patient.last_login_at is None
        login(client, "patient@example.org")
        session.refresh(patient)
        assert patient.last_login_at is not None


class TestTokenLifecycle:
    def test_me_requires_authentication(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_returns_the_signed_in_account(self, client, patient):
        headers = auth_header(client, "patient@example.org")
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.get_json()["email"] == "patient@example.org"

    def test_refresh_issues_a_new_access_token(self, client, patient):
        login(client, "patient@example.org")
        response = client.post("/api/auth/refresh")
        assert response.status_code == 200
        assert response.get_json()["access_token"]

    def test_refresh_rotates_the_token(self, client, patient):
        """Each refresh issues a new token and blocklists the one presented.

        Rotation is what limits a stolen refresh token to a single use. How long the
        superseded token remains usable is covered by the two grace-period tests below:
        briefly, so a concurrent second tab is not signed out, and not a moment longer.
        """

        login(client, "patient@example.org")
        first_cookie = client.get_cookie("bloodnet_refresh", path="/api/auth")
        assert first_cookie is not None
        original_value = first_cookie.value

        assert client.post("/api/auth/refresh").status_code == 200

        rotated = client.get_cookie("bloodnet_refresh", path="/api/auth")
        assert rotated.value != original_value

        blocklisted = self._blocklist_reasons(patient)
        assert blocklisted == ["rotated"]

    @staticmethod
    def _blocklist_reasons(user):
        import sqlalchemy as sa

        from app.extensions import db
        from app.models import TokenBlocklist

        return [
            reason.value
            for reason in db.session.scalars(
                sa.select(TokenBlocklist.reason).where(TokenBlocklist.user_id == user.id)
            ).all()
        ]

    def test_access_token_is_not_accepted_on_the_refresh_endpoint(self, client, patient):
        headers = auth_header(client, "patient@example.org")
        client.delete_cookie("bloodnet_refresh", path="/api/auth")
        response = client.post("/api/auth/refresh", headers=headers)
        assert response.status_code == 401

    def test_a_rotated_token_still_works_briefly_so_a_race_does_not_sign_you_out(
        self, client, patient
    ):
        """Two tabs refreshing at once must not end the session.

        Rotation blocklists the client's own previous token on every refresh. With no
        leeway, a second request already in flight with that same cookie is rejected and
        the user is signed out for doing nothing wrong. React StrictMode surfaced exactly
        this by mounting the provider twice.

        The grace period is short, so a token stolen and used later is still refused. That
        is asserted separately below by disabling the window.
        """

        login(client, "patient@example.org")
        original = client.get_cookie("bloodnet_refresh", path="/api/auth").value

        assert client.post("/api/auth/refresh").status_code == 200

        # Replay the superseded token, as an in-flight second tab would.
        client.set_cookie("bloodnet_refresh", original, path="/api/auth")
        assert client.post("/api/auth/refresh").status_code == 200

    def test_a_rotated_token_is_refused_once_the_grace_period_has_passed(
        self, app, client, patient
    ):
        login(client, "patient@example.org")
        original = client.get_cookie("bloodnet_refresh", path="/api/auth").value
        assert client.post("/api/auth/refresh").status_code == 200

        # Collapsing the window to zero is equivalent to the token having been revoked
        # long ago, without making the test sleep.
        app.config["JWT_REFRESH_REUSE_GRACE_SECONDS"] = 0
        try:
            client.set_cookie("bloodnet_refresh", original, path="/api/auth")
            replay = client.post("/api/auth/refresh")
            assert replay.status_code == 401
            assert replay.get_json()["error"]["code"] == "token_revoked"
        finally:
            app.config["JWT_REFRESH_REUSE_GRACE_SECONDS"] = 20

    def test_logout_revokes_the_refresh_token_immediately_with_no_grace(
        self, client, patient
    ):
        """Logout gets no leeway at all, or the button would be a lie.

        This is why the blocklist records why a token was revoked. The grace period that
        makes rotation survivable must not apply here: a stolen token that still worked
        for twenty seconds after signing out would defeat the point of signing out.
        """

        login(client, "patient@example.org")
        original = client.get_cookie("bloodnet_refresh", path="/api/auth").value

        assert client.post("/api/auth/logout").status_code == 200

        # The cookie is cleared, but the real check is that the token itself is dead even
        # if a copy was kept - immediately, not after a delay.
        client.set_cookie("bloodnet_refresh", original, path="/api/auth")
        response = client.post("/api/auth/refresh")
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "token_revoked"

    def test_deactivation_takes_effect_immediately_not_at_token_expiry(
        self, client, session, patient
    ):
        """A still-valid access token must stop working the moment the account is off.

        This is the reason the user lookup hits the database on every request. Without
        it, a deactivated account keeps full access until its access token expires.
        """

        headers = auth_header(client, "patient@example.org")
        assert client.get("/api/auth/me", headers=headers).status_code == 200

        patient.is_active = False
        session.commit()

        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "account_unavailable"


class TestPasswordChange:
    def test_requires_the_current_password(self, client, patient):
        headers = auth_header(client, "patient@example.org")
        response = client.patch(
            "/api/auth/me/password",
            headers=headers,
            json={"current_password": "wrong", "new_password": VALID_PASSWORD},
        )
        assert response.status_code == 401

    def test_changes_the_password(self, client, patient):
        headers = auth_header(client, "patient@example.org")
        response = client.patch(
            "/api/auth/me/password",
            headers=headers,
            json={"current_password": TEST_PASSWORD, "new_password": VALID_PASSWORD},
        )
        assert response.status_code == 200

        assert login(client, "patient@example.org", TEST_PASSWORD).status_code == 401
        assert login(client, "patient@example.org", VALID_PASSWORD).status_code == 200

    def test_new_password_must_satisfy_the_policy(self, client, patient):
        headers = auth_header(client, "patient@example.org")
        response = client.patch(
            "/api/auth/me/password",
            headers=headers,
            json={"current_password": TEST_PASSWORD, "new_password": "tiny"},
        )
        assert response.status_code == 422
