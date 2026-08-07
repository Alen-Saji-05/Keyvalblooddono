"""The network summary: the four figures the brief asks for."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models import BloodGroup, DonorStatus, Notification, RequestStatus

from .conftest import auth_header, make_donor, make_request_row, make_user
from app.models import UserRole


class TestNetworkSummary:
    def test_the_four_required_figures(self, client, session, admin, patient):
        """One fulfilled request, one part-met, one untouched, with a mixed response rate."""

        donors = [
            make_donor(name=f"D{i}", phone=f"9930{i:06d}", email=f"sum{i}@example.org")
            for i in range(4)
        ]
        # Two donors who cannot give right now, so eligible and registered differ.
        donors.append(
            make_donor(
                name="Unavailable",
                phone="9930900001",
                email="sum-u@example.org",
                status=DonorStatus.UNAVAILABLE_MEDICAL,
            )
        )
        donors.append(
            make_donor(
                name="Underweight",
                phone="9930900002",
                email="sum-w@example.org",
                weight_kg=Decimal("40.00"),
            )
        )
        session.add_all(donors)
        session.flush()

        fulfilled = make_request_row(author_id=patient.id, units_required=2)
        partial = make_request_row(author_id=patient.id, units_required=4)
        untouched = make_request_row(author_id=patient.id, units_required=1)
        session.add_all([fulfilled, partial, untouched])
        session.flush()

        # Four notifications, two answered.
        session.add_all(
            [
                Notification(donor_id=donors[0].id, request_id=fulfilled.id, responded=False),
                Notification(donor_id=donors[1].id, request_id=fulfilled.id, responded=False),
                Notification(donor_id=donors[2].id, request_id=partial.id, responded=False),
                Notification(donor_id=donors[3].id, request_id=partial.id, responded=False),
            ]
        )
        session.commit()

        headers = auth_header(client, "admin@example.org")

        # Two donors fill the two-unit request; one gives one of the four-unit request.
        for donor, request in ((donors[0], fulfilled), (donors[1], fulfilled), (donors[2], partial)):
            response = client.post(
                f"/api/requests/{request.id}/donations",
                headers=headers,
                json={
                    "donor_id": donor.id,
                    "units_given": 1,
                    "donation_date": date.today().isoformat(),
                },
            )
            assert response.status_code == 201, response.get_json()

        body = client.get("/api/summary", headers=headers).get_json()

        assert body["scope"] == "network"

        # Total donations arranged.
        assert body["total_donations"] == 3
        assert body["total_units_donated"] == 3

        # Fulfilled against unfulfilled, with unfulfilled split so the two very different
        # situations are distinguishable.
        assert body["requests_total"] == 3
        assert body["requests_fulfilled"] == 1
        assert body["requests_partially_fulfilled"] == 1
        assert body["requests_open"] == 1
        assert body["requests_unfulfilled"] == 2

        # Response rate. Recording a donation counts as a response, so the three donors
        # who gave are all responders out of four notified.
        assert body["notifications_sent"] == 4
        assert body["notifications_responded"] == 3
        assert body["donor_response_rate"] == 75.0

        # Donors eligible right now, which is three different numbers from registered.
        #
        # Six donors registered. Five are marked available - the medically unavailable one
        # is not. But only one is eligible to give right now: the three who donated a
        # moment ago are inside their cooldown, and the sixth is under the weight
        # threshold. This is the figure the brief asks for and the reason it cannot be
        # approximated by counting rows with status 'available'.
        assert body["donors_registered"] == 6
        assert body["donors_available"] == 5
        assert body["donors_eligible_now"] == 1

    def test_an_empty_network_reports_zeroes_rather_than_failing(self, client, admin):
        body = client.get(
            "/api/summary", headers=auth_header(client, "admin@example.org")
        ).get_json()
        assert body["total_donations"] == 0
        assert body["requests_total"] == 0
        assert body["donor_response_rate"] == 0.0

    def test_eligible_count_matches_the_broadcast_selector(
        self, client, session, admin, patient
    ):
        """The point of defining eligibility once: these two must never disagree."""

        session.add_all(
            [
                make_donor(phone="9931000001", email="m1@example.org"),
                make_donor(phone="9931000002", email="m2@example.org"),
                make_donor(
                    phone="9931000003",
                    email="m3@example.org",
                    last_donation_date=date.today() - timedelta(days=5),
                ),
            ]
        )
        request_row = make_request_row(author_id=patient.id)
        session.add(request_row)
        session.commit()

        headers = auth_header(client, "admin@example.org")

        summary = client.get("/api/summary", headers=headers).get_json()
        broadcast = client.post(
            f"/api/requests/{request_row.id}/broadcast", headers=headers
        ).get_json()

        assert summary["donors_eligible_now"] == broadcast["eligible_total"] == 2

    def test_demand_by_blood_group_reports_every_group(self, client, session, admin, patient):
        request_row = make_request_row(
            author_id=patient.id, blood_group=BloodGroup.AB_NEGATIVE, units_required=5
        )
        session.add(request_row)
        session.commit()

        body = client.get(
            "/api/summary", headers=auth_header(client, "admin@example.org")
        ).get_json()

        assert len(body["demand_by_blood_group"]) == 8
        by_group = {row["blood_group"]: row for row in body["demand_by_blood_group"]}
        assert by_group["AB-"]["open_units_needed"] == 5
        assert by_group["O+"]["open_units_needed"] == 0


class TestScopedSummary:
    def test_a_patient_sees_only_their_own_requests(self, client, session, patient):
        other = make_user(UserRole.PATIENT, "second.patient@example.org")
        session.add(other)
        session.flush()
        session.add_all(
            [
                make_request_row(author_id=patient.id),
                make_request_row(author_id=other.id),
                make_request_row(author_id=other.id),
            ]
        )
        session.commit()

        body = client.get(
            "/api/summary", headers=auth_header(client, "patient@example.org")
        ).get_json()

        assert body["scope"] == "own_requests"
        assert body["requests_total"] == 1

    def test_a_patient_still_sees_network_wide_donor_counts(self, client, session, patient):
        """Aggregate and identity-free, and the figure that says whether help exists."""

        session.add(make_donor(phone="9932000001", email="pool@example.org"))
        session.commit()

        body = client.get(
            "/api/summary", headers=auth_header(client, "patient@example.org")
        ).get_json()
        assert body["donors_eligible_now"] == 1

    def test_donors_get_no_summary(self, client, donor_account):
        response = client.get(
            "/api/summary", headers=auth_header(client, "donor@example.org")
        )
        assert response.status_code == 403
