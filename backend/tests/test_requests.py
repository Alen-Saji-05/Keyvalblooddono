"""Blood requests: who may create them, who may see them, and what they see."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import Notification, RequestStatus, User, UserRole

from .conftest import auth_header, make_donor, make_request_row, make_user


def valid_request(**overrides) -> dict:
    payload = {
        "patient_name": "Grace Mathew",
        "blood_group": "O-",
        "hospital": "Riverside Medical Centre",
        "place": "Thrissur",
        "contact_phone": "9800002222",
        "units_required": 3,
        "needed_by_date": (date.today() + timedelta(days=5)).isoformat(),
    }
    payload.update(overrides)
    return payload


class TestCreation:
    def test_a_patient_can_file_a_request(self, client, patient):
        response = client.post(
            "/api/requests",
            headers=auth_header(client, "patient@example.org"),
            json=valid_request(),
        )
        assert response.status_code == 201
        body = response.get_json()
        assert body["status"] == "open"
        assert body["units_fulfilled"] == 0
        assert body["units_outstanding"] == 3
        assert body["created_by_user_id"] == patient.id

    def test_a_donor_cannot_file_a_request(self, client, donor_account):
        response = client.post(
            "/api/requests",
            headers=auth_header(client, "donor@example.org"),
            json=valid_request(),
        )
        assert response.status_code == 403

    def test_the_author_is_taken_from_the_token_not_the_body(self, client, patient, admin):
        """Otherwise a patient could attach their request to another account."""

        response = client.post(
            "/api/requests",
            headers=auth_header(client, "patient@example.org"),
            json=valid_request(created_by_user_id=admin.id),
        )
        assert response.status_code == 422

    def test_a_past_deadline_is_refused(self, client, patient):
        response = client.post(
            "/api/requests",
            headers=auth_header(client, "patient@example.org"),
            json=valid_request(needed_by_date=(date.today() - timedelta(days=1)).isoformat()),
        )
        assert response.status_code == 422

    def test_an_implausible_unit_count_is_refused(self, client, patient):
        response = client.post(
            "/api/requests",
            headers=auth_header(client, "patient@example.org"),
            json=valid_request(units_required=500),
        )
        assert response.status_code == 422

    def test_zero_units_is_refused(self, client, patient):
        response = client.post(
            "/api/requests",
            headers=auth_header(client, "patient@example.org"),
            json=valid_request(units_required=0),
        )
        assert response.status_code == 422


class TestVisibility:
    def _two_patients(self, session):
        second = make_user(UserRole.PATIENT, "other.patient@example.org")
        session.add(second)
        session.commit()
        return second

    def test_a_patient_sees_only_their_own_requests(self, client, session, patient):
        other = self._two_patients(session)
        session.add_all(
            [
                make_request_row(author_id=patient.id, patient_name="Mine"),
                make_request_row(author_id=other.id, patient_name="Theirs"),
            ]
        )
        session.commit()

        body = client.get(
            "/api/requests", headers=auth_header(client, "patient@example.org")
        ).get_json()

        assert body["total"] == 1
        assert body["items"][0]["patient_name"] == "Mine"

    def test_an_admin_sees_every_request(self, client, session, patient, admin):
        other = self._two_patients(session)
        session.add_all(
            [
                make_request_row(author_id=patient.id),
                make_request_row(author_id=other.id),
            ]
        )
        session.commit()

        body = client.get(
            "/api/requests", headers=auth_header(client, "admin@example.org")
        ).get_json()
        assert body["total"] == 2

    def test_a_donor_sees_only_requests_they_were_notified_about(
        self, client, session, patient, donor_account
    ):
        donor, _user = donor_account
        notified = make_request_row(author_id=patient.id, patient_name="Notified")
        unnotified = make_request_row(author_id=patient.id, patient_name="Not notified")
        session.add_all([notified, unnotified])
        session.flush()
        session.add(Notification(donor_id=donor.id, request_id=notified.id))
        session.commit()

        body = client.get(
            "/api/requests", headers=auth_header(client, "donor@example.org")
        ).get_json()

        assert body["total"] == 1
        assert body["items"][0]["patient_name"] == "Notified"

    def test_another_patients_request_is_404_not_403(self, client, session, patient):
        """403 would confirm the request exists and let anyone probe for ids."""

        other = self._two_patients(session)
        theirs = make_request_row(author_id=other.id)
        session.add(theirs)
        session.commit()

        response = client.get(
            f"/api/requests/{theirs.id}", headers=auth_header(client, "patient@example.org")
        )
        assert response.status_code == 404


class TestFilters:
    def test_expired_requests_are_hidden_by_default(self, client, session, patient):
        session.add_all(
            [
                make_request_row(author_id=patient.id, patient_name="Current"),
                make_request_row(
                    author_id=patient.id,
                    patient_name="Overdue",
                    needed_by_date=date.today() - timedelta(days=3),
                ),
            ]
        )
        session.commit()

        headers = auth_header(client, "patient@example.org")

        default = client.get("/api/requests", headers=headers).get_json()
        assert default["total"] == 1
        assert default["items"][0]["patient_name"] == "Current"

        including = client.get("/api/requests?include_expired=true", headers=headers).get_json()
        assert including["total"] == 2
        overdue = next(i for i in including["items"] if i["patient_name"] == "Overdue")
        assert overdue["is_expired"] is True

    def test_requests_are_ordered_by_soonest_deadline(self, client, session, patient):
        session.add_all(
            [
                make_request_row(
                    author_id=patient.id,
                    patient_name="Later",
                    needed_by_date=date.today() + timedelta(days=20),
                ),
                make_request_row(
                    author_id=patient.id,
                    patient_name="Sooner",
                    needed_by_date=date.today() + timedelta(days=2),
                ),
            ]
        )
        session.commit()

        body = client.get(
            "/api/requests", headers=auth_header(client, "patient@example.org")
        ).get_json()
        assert [i["patient_name"] for i in body["items"]] == ["Sooner", "Later"]

    def test_filter_by_status(self, client, session, patient):
        session.add_all(
            [
                make_request_row(author_id=patient.id),
                make_request_row(
                    author_id=patient.id,
                    units_required=1,
                    units_fulfilled=1,
                    status=RequestStatus.FULFILLED,
                ),
            ]
        )
        session.commit()

        body = client.get(
            "/api/requests?status=fulfilled", headers=auth_header(client, "patient@example.org")
        ).get_json()
        assert body["total"] == 1


class TestRequestDetailDisclosure:
    def test_a_patient_sees_donation_progress_without_donor_identities(
        self, client, session, patient, admin, blood_request
    ):
        """Donors who gave never agreed to be named to the patient."""

        donor = make_donor(name="Ananya Rao", phone="9920000001", email="ident@example.org")
        session.add(donor)
        session.commit()

        client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 1,
                "donation_date": date.today().isoformat(),
            },
        )

        response = client.get(
            f"/api/requests/{blood_request.id}",
            headers=auth_header(client, "patient@example.org"),
        )
        assert response.status_code == 200
        body = response.get_json()

        assert body["units_fulfilled"] == 1
        assert len(body["donations"]) == 1
        assert body["donations"][0]["units_given"] == 1
        assert body["donations"][0]["donor_name"] is None
        assert body["donations"][0]["donor_id"] is None
        assert "Ananya Rao" not in response.get_data(as_text=True)
        # Notification detail is administrator-only.
        assert "notifications" not in body

    def test_an_admin_sees_donor_identities_and_notifications(
        self, client, session, admin, blood_request
    ):
        donor = make_donor(name="Ananya Rao", phone="9920001001", email="ident2@example.org")
        session.add(donor)
        session.flush()
        session.add(Notification(donor_id=donor.id, request_id=blood_request.id))
        session.commit()

        client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 1,
                "donation_date": date.today().isoformat(),
            },
        )

        body = client.get(
            f"/api/requests/{blood_request.id}", headers=auth_header(client, "admin@example.org")
        ).get_json()

        assert body["donations"][0]["donor_name"] == "Ananya Rao"
        assert len(body["notifications"]) == 1

    def test_outreach_counts_are_visible_to_the_patient(
        self, client, session, patient, admin, blood_request
    ):
        """So a patient can see the request is being worked on before any units arrive."""

        session.add_all(
            [
                make_donor(phone="9920002001", email="c1@example.org"),
                make_donor(phone="9920002002", email="c2@example.org"),
            ]
        )
        session.commit()

        client.post(
            f"/api/requests/{blood_request.id}/broadcast",
            headers=auth_header(client, "admin@example.org"),
        )

        body = client.get(
            f"/api/requests/{blood_request.id}",
            headers=auth_header(client, "patient@example.org"),
        ).get_json()

        assert body["notified_count"] == 2
        assert body["responded_count"] == 0


class TestDonorInboxAndResponding:
    def test_a_donor_sees_the_broadcast_in_their_inbox(
        self, client, session, admin, donor_account, blood_request
    ):
        donor, _user = donor_account
        session.add(Notification(donor_id=donor.id, request_id=blood_request.id))
        session.commit()

        body = client.get(
            "/api/me/notifications", headers=auth_header(client, "donor@example.org")
        ).get_json()

        assert body["total"] == 1
        item = body["items"][0]
        assert item["hospital"] == blood_request.hospital
        assert item["units_outstanding"] == 3
        assert item["responded"] is False

    def test_a_donor_can_respond_to_their_own_notification(
        self, client, session, donor_account, blood_request
    ):
        donor, _user = donor_account
        notification = Notification(donor_id=donor.id, request_id=blood_request.id)
        session.add(notification)
        session.commit()

        response = client.post(
            f"/api/notifications/{notification.id}/respond",
            headers=auth_header(client, "donor@example.org"),
        )
        assert response.status_code == 200
        assert response.get_json()["responded"] is True

    def test_responding_twice_keeps_the_original_timestamp(
        self, client, session, donor_account, blood_request
    ):
        """Otherwise reopening a message would silently corrupt response-time figures."""

        donor, _user = donor_account
        notification = Notification(donor_id=donor.id, request_id=blood_request.id)
        session.add(notification)
        session.commit()

        url = f"/api/notifications/{notification.id}/respond"
        headers = auth_header(client, "donor@example.org")

        first = client.post(url, headers=headers).get_json()["response_at"]
        second = client.post(url, headers=headers).get_json()["response_at"]
        assert first == second

    def test_a_donor_cannot_respond_on_behalf_of_another_donor(
        self, client, session, donor_account, blood_request
    ):
        other = make_donor(phone="9921000001", email="someone@example.org")
        session.add(other)
        session.flush()
        notification = Notification(donor_id=other.id, request_id=blood_request.id)
        session.add(notification)
        session.commit()

        response = client.post(
            f"/api/notifications/{notification.id}/respond",
            headers=auth_header(client, "donor@example.org"),
        )
        assert response.status_code == 403

    def test_an_admin_can_record_a_response_taken_by_telephone(
        self, client, session, admin, donor_account, blood_request
    ):
        """Without this the response rate would only ever count portal users."""

        donor, _user = donor_account
        notification = Notification(donor_id=donor.id, request_id=blood_request.id)
        session.add(notification)
        session.commit()

        response = client.post(
            f"/api/notifications/{notification.id}/respond",
            headers=auth_header(client, "admin@example.org"),
        )
        assert response.status_code == 200

    def test_a_donor_sees_their_own_donation_history(
        self, client, session, admin, donor_account, blood_request
    ):
        donor, _user = donor_account

        client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 2,
                "donation_date": date.today().isoformat(),
            },
        )

        body = client.get(
            "/api/me/donations", headers=auth_header(client, "donor@example.org")
        ).get_json()
        assert len(body["items"]) == 1
        assert body["items"][0]["units_given"] == 2
