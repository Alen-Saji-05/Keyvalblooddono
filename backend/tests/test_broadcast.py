"""Broadcast: who gets selected, who gets skipped, and what is reported back."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import sqlalchemy as sa

from app.models import BloodGroup, DonorStatus, Notification, RequestStatus, Sex

from .conftest import auth_header, make_donor, make_request_row


def broadcast(client, request_id: int, **options):
    return client.post(
        f"/api/requests/{request_id}/broadcast",
        headers=auth_header(client, "admin@example.org"),
        json=options or None,
    )


class TestSelection:
    def test_only_eligible_donors_of_the_matching_group_are_notified(
        self, client, admin, session, blood_request
    ):
        """blood_request needs O negative. Everyone below is excluded for one reason."""

        donors = [
            make_donor(name="Eligible", phone="9901000001", email="e1@example.org"),
            make_donor(
                name="Wrong group",
                blood_group=BloodGroup.A_POSITIVE,
                phone="9901000002",
                email="e2@example.org",
            ),
            make_donor(
                name="Travelling",
                status=DonorStatus.UNAVAILABLE_TRAVELING,
                phone="9901000003",
                email="e3@example.org",
            ),
            make_donor(
                name="In cooldown",
                last_donation_date=date.today() - timedelta(days=10),
                phone="9901000004",
                email="e4@example.org",
            ),
            make_donor(
                name="Underweight",
                weight_kg=Decimal("40.00"),
                phone="9901000005",
                email="e5@example.org",
            ),
            make_donor(
                name="Too old",
                date_of_birth=date.today() - timedelta(days=70 * 365),
                phone="9901000006",
                email="e6@example.org",
            ),
        ]
        session.add_all(donors)
        session.commit()

        response = broadcast(client, blood_request.id)
        assert response.status_code == 200, response.get_json()
        body = response.get_json()

        assert body["notified"] == 1
        assert body["eligible_total"] == 1
        assert body["targeted_blood_groups"] == ["O-"]

        notified = session.scalars(
            sa.select(Notification.donor_id).where(
                Notification.request_id == blood_request.id
            )
        ).all()
        assert len(notified) == 1
        assert session.get(type(donors[0]), notified[0]).name == "Eligible"

    def test_a_first_time_donor_is_included(self, client, admin, session, blood_request):
        """The null branch of the cooldown check, which is easy to lose to SQL null logic."""

        session.add(make_donor(phone="9901001001", email="f@example.org", last_donation_date=None))
        session.commit()

        assert broadcast(client, blood_request.id).get_json()["notified"] == 1

    def test_a_donor_just_outside_the_cooldown_is_included(
        self, client, admin, session, blood_request
    ):
        session.add(
            make_donor(
                phone="9901002001",
                email="g@example.org",
                sex=Sex.MALE,
                last_donation_date=date.today() - timedelta(days=91),
            )
        )
        session.commit()
        assert broadcast(client, blood_request.id).get_json()["notified"] == 1

    def test_female_donors_use_the_longer_cooldown(
        self, client, admin, session, blood_request
    ):
        """100 days is outside the male interval but inside the female one."""

        session.add(
            make_donor(
                phone="9901003001",
                email="h@example.org",
                sex=Sex.FEMALE,
                last_donation_date=date.today() - timedelta(days=100),
            )
        )
        session.commit()
        assert broadcast(client, blood_request.id).get_json()["notified"] == 0


class TestCompatibilityWidening:
    def test_exact_match_is_the_default(self, client, admin, session):
        """The behaviour the brief describes: matching blood group."""

        request_row = make_request_row(blood_group=BloodGroup.A_POSITIVE)
        session.add(request_row)
        session.add_all(
            [
                make_donor(
                    blood_group=BloodGroup.O_NEGATIVE, phone="9902000001", email="o@example.org"
                ),
                make_donor(
                    blood_group=BloodGroup.A_POSITIVE, phone="9902000002", email="a@example.org"
                ),
            ]
        )
        session.commit()

        body = broadcast(client, request_row.id).get_json()
        assert body["notified"] == 1
        assert body["targeted_blood_groups"] == ["A+"]

    def test_opting_in_widens_to_compatible_donors(self, client, admin, session):
        request_row = make_request_row(blood_group=BloodGroup.A_POSITIVE)
        session.add(request_row)
        session.add_all(
            [
                make_donor(
                    blood_group=BloodGroup.O_NEGATIVE, phone="9902001001", email="p@example.org"
                ),
                make_donor(
                    blood_group=BloodGroup.A_POSITIVE, phone="9902001002", email="q@example.org"
                ),
                make_donor(
                    blood_group=BloodGroup.B_POSITIVE, phone="9902001003", email="r@example.org"
                ),
            ]
        )
        session.commit()

        body = broadcast(client, request_row.id, include_compatible=True).get_json()
        # O- and A+ can give to A+; B+ cannot.
        assert body["notified"] == 2
        assert set(body["targeted_blood_groups"]) == {"O-", "O+", "A-", "A+"}

    def test_o_negative_recipient_stays_narrow_even_when_widened(
        self, client, admin, session, blood_request
    ):
        """Widening must not invert the direction of the compatibility matrix."""

        session.add_all(
            [
                make_donor(
                    blood_group=BloodGroup.O_NEGATIVE, phone="9902002001", email="s@example.org"
                ),
                make_donor(
                    blood_group=BloodGroup.AB_POSITIVE, phone="9902002002", email="t@example.org"
                ),
            ]
        )
        session.commit()

        body = broadcast(client, blood_request.id, include_compatible=True).get_json()
        assert body["notified"] == 1
        assert body["targeted_blood_groups"] == ["O-"]


class TestPlaceNarrowing:
    def test_broadcast_can_be_restricted_to_a_locality(
        self, client, admin, session, blood_request
    ):
        session.add_all(
            [
                make_donor(place="Kochi", phone="9903000001", email="u@example.org"),
                make_donor(place="Kozhikode", phone="9903000002", email="v@example.org"),
            ]
        )
        session.commit()

        assert broadcast(client, blood_request.id, place="Kochi").get_json()["notified"] == 1


class TestRepeatBroadcast:
    def test_donors_already_notified_are_skipped_not_notified_twice(
        self, client, admin, session, blood_request
    ):
        """Re-broadcasting a request still short of units is normal and must be safe."""

        session.add(make_donor(phone="9904000001", email="w@example.org"))
        session.commit()

        first = broadcast(client, blood_request.id).get_json()
        assert first["notified"] == 1
        assert first["already_notified"] == 0

        second = broadcast(client, blood_request.id).get_json()
        assert second["notified"] == 0
        assert second["already_notified"] == 1
        assert second["eligible_total"] == 1

        count = session.scalar(
            sa.select(sa.func.count()).select_from(Notification).where(
                Notification.request_id == blood_request.id
            )
        )
        assert count == 1, "a duplicate notification would inflate the response rate"

    def test_a_newly_registered_donor_is_picked_up_by_a_second_broadcast(
        self, client, admin, session, blood_request
    ):
        session.add(make_donor(phone="9904001001", email="x@example.org"))
        session.commit()
        broadcast(client, blood_request.id)

        session.add(make_donor(phone="9904001002", email="y@example.org"))
        session.commit()

        second = broadcast(client, blood_request.id).get_json()
        assert second["notified"] == 1
        assert second["already_notified"] == 1


class TestBroadcastGuards:
    def test_a_fulfilled_request_cannot_be_broadcast(
        self, client, admin, session, blood_request
    ):
        """Sending donors to a hospital that no longer needs them wastes a donation."""

        donor = make_donor(phone="9905000001", email="z@example.org")
        session.add(donor)
        session.commit()

        client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 3,
                "donation_date": date.today().isoformat(),
            },
        )

        response = broadcast(client, blood_request.id)
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "request_already_fulfilled"

    def test_a_partially_fulfilled_request_can_still_be_broadcast(
        self, client, admin, session, blood_request
    ):
        donor = make_donor(phone="9905001001", email="aa@example.org")
        second = make_donor(phone="9905001002", email="bb@example.org")
        session.add_all([donor, second])
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
        session.expire_all()
        assert (
            session.get(type(blood_request), blood_request.id).status
            is RequestStatus.PARTIALLY_FULFILLED
        )

        assert broadcast(client, blood_request.id).status_code == 200

    def test_broadcasting_with_no_eligible_donors_reports_zero_rather_than_failing(
        self, client, admin, blood_request
    ):
        body = broadcast(client, blood_request.id).get_json()
        assert body == {
            "request_id": blood_request.id,
            "notified": 0,
            "already_notified": 0,
            "eligible_total": 0,
            "delivery_failures": 0,
            "targeted_blood_groups": ["O-"],
        }


class TestBroadcastAuthorisation:
    def test_a_patient_cannot_broadcast_their_own_request(
        self, client, patient, blood_request
    ):
        response = client.post(
            f"/api/requests/{blood_request.id}/broadcast",
            headers=auth_header(client, "patient@example.org"),
        )
        assert response.status_code == 403

    def test_a_donor_cannot_broadcast(self, client, donor_account, blood_request):
        response = client.post(
            f"/api/requests/{blood_request.id}/broadcast",
            headers=auth_header(client, "donor@example.org"),
        )
        assert response.status_code == 403
