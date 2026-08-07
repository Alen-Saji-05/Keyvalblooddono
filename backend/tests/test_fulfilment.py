"""Fulfilment: the multi-donor case the whole design exists for."""

from __future__ import annotations

import threading
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import BloodRequest, Donation, RequestStatus, User
from app.schemas.request import DonationCreateIn
from app.services.donations import record_donation
from app.services.fulfilment import derive_status, recompute_request_fulfilment

from .conftest import auth_header, make_donor, make_request_row


class TestStatusDerivation:
    @pytest.mark.parametrize(
        "fulfilled, required, expected",
        [
            (0, 3, RequestStatus.OPEN),
            (1, 3, RequestStatus.PARTIALLY_FULFILLED),
            (2, 3, RequestStatus.PARTIALLY_FULFILLED),
            (3, 3, RequestStatus.FULFILLED),
            # An overshoot is fulfilled, not stuck in partial. A final donor giving two
            # units against one outstanding is a met request, not a broken one.
            (4, 3, RequestStatus.FULFILLED),
        ],
    )
    def test_status_follows_the_arithmetic(self, fulfilled, required, expected):
        assert derive_status(fulfilled, required) is expected


class TestMultiDonorFulfilment:
    def test_three_donors_fill_a_three_unit_request_one_unit_at_a_time(
        self, client, admin, session, blood_request
    ):
        """The core requirement: a request stays open until the units accumulate."""

        donors = [
            make_donor(name=f"Donor {i}", phone=f"990000100{i}", email=f"d{i}@example.org")
            for i in range(3)
        ]
        session.add_all(donors)
        session.commit()
        donor_ids = [d.id for d in donors]

        headers = auth_header(client, "admin@example.org")
        url = f"/api/requests/{blood_request.id}/donations"

        expected = [
            (1, "partially_fulfilled"),
            (2, "partially_fulfilled"),
            (3, "fulfilled"),
        ]

        for donor_id, (units_so_far, status) in zip(donor_ids, expected):
            response = client.post(
                url,
                headers=headers,
                json={
                    "donor_id": donor_id,
                    "units_given": 1,
                    "donation_date": date.today().isoformat(),
                },
            )
            assert response.status_code == 201, response.get_json()
            body = response.get_json()
            assert body["units_fulfilled"] == units_so_far
            assert body["units_outstanding"] == 3 - units_so_far
            assert body["status"] == status
            assert body["donation_count"] == units_so_far

    def test_a_single_donor_can_overshoot_and_the_request_is_fulfilled(
        self, client, admin, session, blood_request
    ):
        donor = make_donor(phone="9900002001", email="over@example.org")
        session.add(donor)
        session.commit()

        response = client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 5,
                "donation_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 201
        body = response.get_json()
        assert body["units_fulfilled"] == 5
        assert body["units_outstanding"] == 0
        assert body["status"] == "fulfilled"

    def test_recorded_total_always_equals_the_sum_of_donations(
        self, client, admin, session, blood_request
    ):
        """units_fulfilled is a cache of SUM(donations), never an independent counter."""

        donors = [
            make_donor(name=f"D{i}", phone=f"990000300{i}", email=f"s{i}@example.org")
            for i in range(4)
        ]
        session.add_all(donors)
        session.commit()

        headers = auth_header(client, "admin@example.org")
        for donor in donors:
            client.post(
                f"/api/requests/{blood_request.id}/donations",
                headers=headers,
                json={
                    "donor_id": donor.id,
                    "units_given": 1,
                    "donation_date": date.today().isoformat(),
                },
            )

        session.expire_all()
        row = session.get(BloodRequest, blood_request.id)
        actual = session.scalar(
            sa.select(sa.func.sum(Donation.units_given)).where(
                Donation.request_id == blood_request.id
            )
        )
        assert row.units_fulfilled == actual == 4

    def test_deleting_a_donation_and_recomputing_lowers_the_total(
        self, client, admin, session, blood_request
    ):
        """Because the total is recomputed rather than incremented, it can go down."""

        donor = make_donor(phone="9900004001", email="rm@example.org")
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
        session.expire_all()
        assert session.get(BloodRequest, blood_request.id).status is RequestStatus.FULFILLED

        session.execute(sa.delete(Donation).where(Donation.request_id == blood_request.id))
        recompute_request_fulfilment(session, blood_request.id)
        session.commit()

        row = session.get(BloodRequest, blood_request.id)
        assert row.units_fulfilled == 0
        assert row.status is RequestStatus.OPEN


class TestSideEffectsOfRecordingADonation:
    def test_donor_last_donation_date_is_stamped(
        self, client, admin, session, blood_request
    ):
        donor = make_donor(phone="9900005001", email="stamp@example.org")
        session.add(donor)
        session.commit()
        assert donor.last_donation_date is None

        client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 1,
                "donation_date": date.today().isoformat(),
            },
        )
        session.refresh(donor)
        assert donor.last_donation_date == date.today()

    def test_backdated_entry_does_not_move_the_cooldown_backwards(
        self, client, admin, session, blood_request
    ):
        """Entering a paper backlog out of order must not make a donor look eligible early."""

        recent = date.today() - timedelta(days=5)
        donor = make_donor(
            phone="9900006001", email="back@example.org", last_donation_date=recent
        )
        session.add(donor)
        session.commit()

        client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 1,
                "donation_date": (date.today() - timedelta(days=40)).isoformat(),
            },
        )
        session.refresh(donor)
        assert donor.last_donation_date == recent

    def test_recording_a_donation_marks_the_notification_responded(
        self, client, admin, session, blood_request
    ):
        """Somebody who turned up and gave has responded, whatever they clicked."""

        from app.models import Notification

        donor = make_donor(phone="9900007001", email="resp@example.org")
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

        notification = session.scalar(
            sa.select(Notification).where(Notification.donor_id == donor.id)
        )
        session.refresh(notification)
        assert notification.responded is True
        assert notification.response_at is not None

    def test_donation_dated_before_the_request_is_refused(
        self, client, admin, session, blood_request
    ):
        donor = make_donor(phone="9900008001", email="early@example.org")
        session.add(donor)
        session.commit()

        response = client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": donor.id,
                "units_given": 1,
                "donation_date": (date.today() - timedelta(days=365)).isoformat(),
            },
        )
        assert response.status_code == 422

    def test_unknown_donor_is_refused(self, client, admin, blood_request):
        response = client.post(
            f"/api/requests/{blood_request.id}/donations",
            headers=auth_header(client, "admin@example.org"),
            json={
                "donor_id": 99999,
                "units_given": 1,
                "donation_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 404


class TestConcurrentDonationRecording:
    def test_two_simultaneous_donations_neither_deadlock_nor_lose_an_update(
        self, app, session, admin
    ):
        """Two administrators recording against the same request at the same moment.

        Without the row lock, both transactions read the pre-existing total and both
        write a value omitting the other's donation, so the request shows one unit when
        two arrived and keeps broadcasting for blood it already has.

        With the lock taken in the wrong order - donation inserted first, exclusive lock
        second - PostgreSQL kills one transaction with a deadlock, because the insert
        already holds a key-share lock on the request that the other's exclusive lock
        must wait for. That is exactly what this test caught.

        It drives the real service function on two separate connections, because both the
        lock and its ordering live there and a single session would exercise neither.
        """

        request_row = make_request_row(units_required=4)
        donor_a = make_donor(phone="9900009001", email="ca@example.org")
        donor_b = make_donor(phone="9900009002", email="cb@example.org")
        session.add_all([request_row, donor_a, donor_b])
        session.commit()

        request_id = request_row.id
        admin_id = admin.id
        donor_ids = [donor_a.id, donor_b.id]

        ready = threading.Barrier(2, timeout=10)
        errors = []

        def record(donor_id: int):
            # The worker runs in its own application context: db.engine resolves through
            # one, and a thread started outside a request has none.
            try:
                with app.app_context(), Session(db.engine) as worker:
                    worker.get(BloodRequest, request_id)
                    # Both threads are inside a live transaction before either writes, so
                    # the two attempts genuinely overlap rather than running in sequence.
                    ready.wait()
                    record_donation(
                        worker,
                        worker.get(BloodRequest, request_id),
                        DonationCreateIn(
                            donor_id=donor_id,
                            units_given=1,
                            donation_date=date.today(),
                        ),
                        worker.get(User, admin_id),
                    )
                    worker.commit()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=record, args=(d,)) for d in donor_ids]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        assert not errors, errors

        session.expire_all()
        row = session.get(BloodRequest, request_id)
        assert row.units_fulfilled == 2, "one donation was lost"
        assert row.status is RequestStatus.PARTIALLY_FULFILLED
