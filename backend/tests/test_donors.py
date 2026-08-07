"""Donor directory: search, edits, availability, and who may see what."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models import BloodGroup, DonorStatus

from .conftest import auth_header, make_donor


def admin_headers(client):
    return auth_header(client, "admin@example.org")


class TestDirectoryIsAdminOnly:
    def test_a_patient_cannot_list_donors(self, client, patient):
        response = client.get("/api/donors", headers=auth_header(client, "patient@example.org"))
        assert response.status_code == 403

    def test_a_donor_cannot_browse_the_directory(self, client, donor_account):
        response = client.get("/api/donors", headers=auth_header(client, "donor@example.org"))
        assert response.status_code == 403

    def test_a_donor_can_read_their_own_record(self, client, donor_account):
        donor, _user = donor_account
        response = client.get(
            f"/api/donors/{donor.id}", headers=auth_header(client, "donor@example.org")
        )
        assert response.status_code == 200
        assert response.get_json()["id"] == donor.id

    def test_a_donor_cannot_read_someone_elses_record(self, client, donor_account, session):
        other = make_donor(phone="9910000001", email="other@example.org")
        session.add(other)
        session.commit()

        response = client.get(
            f"/api/donors/{other.id}", headers=auth_header(client, "donor@example.org")
        )
        assert response.status_code == 403


class TestSearch:
    def _seed(self, session):
        session.add_all(
            [
                make_donor(
                    name="Ananya Rao",
                    blood_group=BloodGroup.O_NEGATIVE,
                    place="Kochi",
                    phone="9911000001",
                    email="ananya@example.org",
                ),
                make_donor(
                    name="Vikram Iyer",
                    blood_group=BloodGroup.A_POSITIVE,
                    place="Kozhikode",
                    phone="9911000002",
                    email="vikram@example.org",
                ),
                make_donor(
                    name="Divya Suresh",
                    blood_group=BloodGroup.O_NEGATIVE,
                    place="Kochi",
                    phone="9911000003",
                    email="divya@example.org",
                    status=DonorStatus.UNAVAILABLE_MEDICAL,
                ),
                make_donor(
                    name="Ravi Chandran",
                    blood_group=BloodGroup.O_NEGATIVE,
                    place="Thrissur",
                    phone="9911000004",
                    email="ravi@example.org",
                    weight_kg=Decimal("40.00"),
                ),
            ]
        )
        session.commit()

    def test_filter_by_blood_group(self, client, admin, session):
        self._seed(session)
        body = client.get("/api/donors?blood_group=O-", headers=admin_headers(client)).get_json()
        assert body["total"] == 3

    def test_filter_by_place_is_case_insensitive(self, client, admin, session):
        self._seed(session)
        body = client.get("/api/donors?place=kochi", headers=admin_headers(client)).get_json()
        assert body["total"] == 2

    def test_filter_by_status(self, client, admin, session):
        self._seed(session)
        body = client.get(
            "/api/donors?status=unavailable_medical", headers=admin_headers(client)
        ).get_json()
        assert body["total"] == 1

    def test_eligible_only_excludes_unavailable_and_underweight(self, client, admin, session):
        """Available and eligible are not the same thing, which is the point of the filter."""

        self._seed(session)
        body = client.get(
            "/api/donors?eligible_only=true", headers=admin_headers(client)
        ).get_json()
        names = {item["name"] for item in body["items"]}
        assert names == {"Ananya Rao", "Vikram Iyer"}

    def test_free_text_search_covers_name_and_place(self, client, admin, session):
        self._seed(session)
        assert (
            client.get("/api/donors?q=ananya", headers=admin_headers(client)).get_json()["total"]
            == 1
        )
        assert (
            client.get("/api/donors?q=thrissur", headers=admin_headers(client)).get_json()[
                "total"
            ]
            == 1
        )

    def test_pagination_caps_the_page_size(self, client, admin, session):
        self._seed(session)
        response = client.get("/api/donors?page_size=5000", headers=admin_headers(client))
        # Rejected rather than silently clamped, so a caller cannot request the entire
        # contact database and be told it succeeded.
        assert response.status_code == 422

    def test_pagination_reports_the_unpaged_total(self, client, admin, session):
        self._seed(session)
        body = client.get("/api/donors?page_size=2", headers=admin_headers(client)).get_json()
        assert len(body["items"]) == 2
        assert body["total"] == 4
        assert body["pages"] == 2


class TestEligibilityIsComputedServerSide:
    def test_reasons_are_returned_not_left_to_the_client(self, client, admin, session):
        donor = make_donor(
            phone="9912000001",
            email="cool@example.org",
            last_donation_date=date.today() - timedelta(days=10),
        )
        session.add(donor)
        session.commit()

        body = client.get(f"/api/donors/{donor.id}", headers=admin_headers(client)).get_json()
        assert body["is_eligible"] is False
        assert body["ineligibility_reasons"]
        assert body["next_eligible_date"] is not None

    def test_an_eligible_donor_reports_no_reasons(self, client, admin, session):
        donor = make_donor(phone="9912001001", email="ok@example.org")
        session.add(donor)
        session.commit()

        body = client.get(f"/api/donors/{donor.id}", headers=admin_headers(client)).get_json()
        assert body["is_eligible"] is True
        assert body["ineligibility_reasons"] == []
        assert body["next_eligible_date"] is None


class TestRegistrationAndEdits:
    def test_admin_registers_a_donor_without_creating_a_login(self, client, admin):
        response = client.post(
            "/api/donors",
            headers=admin_headers(client),
            json={
                "name": "Walk In Donor",
                "blood_group": "B+",
                "sex": "male",
                "date_of_birth": (date.today() - timedelta(days=30 * 365)).isoformat(),
                "weight_kg": "72.0",
                "phone": "9913000001",
                "place": "Kollam",
            },
        )
        assert response.status_code == 201
        assert response.get_json()["is_eligible"] is True

    def test_duplicate_phone_is_refused(self, client, admin, session):
        session.add(make_donor(phone="9913001001", email="dup@example.org"))
        session.commit()

        response = client.post(
            "/api/donors",
            headers=admin_headers(client),
            json={
                "name": "Duplicate",
                "blood_group": "B+",
                "sex": "male",
                "date_of_birth": (date.today() - timedelta(days=30 * 365)).isoformat(),
                "weight_kg": "72.0",
                "phone": "9913001001",
                "place": "Kollam",
            },
        )
        assert response.status_code == 409

    def test_blood_group_cannot_be_patched(self, client, admin, session):
        """An eligibility input is not something a stray edit should silently change."""

        donor = make_donor(phone="9913002001", email="bg@example.org")
        session.add(donor)
        session.commit()

        response = client.patch(
            f"/api/donors/{donor.id}",
            headers=admin_headers(client),
            json={"blood_group": "AB+"},
        )
        assert response.status_code == 422

    def test_empty_patch_is_refused(self, client, admin, session):
        donor = make_donor(phone="9913003001", email="empty@example.org")
        session.add(donor)
        session.commit()

        response = client.patch(
            f"/api/donors/{donor.id}", headers=admin_headers(client), json={}
        )
        assert response.status_code == 422


class TestAvailabilityStatus:
    def test_marking_unavailable_records_the_reason_and_the_note(
        self, client, admin, session
    ):
        donor = make_donor(phone="9914000001", email="away@example.org")
        session.add(donor)
        session.commit()

        body = client.patch(
            f"/api/donors/{donor.id}/status",
            headers=admin_headers(client),
            json={"status": "unavailable_traveling", "note": "Overseas until December."},
        ).get_json()

        assert body["status"] == "unavailable_traveling"
        assert body["status_note"] == "Overseas until December."
        assert body["is_eligible"] is False

    def test_returning_to_available_clears_the_note(self, client, admin, session):
        """A stale explanation next to an available donor would mislead a coordinator."""

        donor = make_donor(
            phone="9914001001",
            email="back@example.org",
            status=DonorStatus.UNAVAILABLE_MOVED,
            status_note="Moved to another state.",
        )
        session.add(donor)
        session.commit()

        body = client.patch(
            f"/api/donors/{donor.id}/status",
            headers=admin_headers(client),
            json={"status": "available"},
        ).get_json()

        assert body["status"] == "available"
        assert body["status_note"] is None
        assert body["is_eligible"] is True

    def test_a_note_on_an_available_donor_is_refused(self, client, admin, session):
        donor = make_donor(phone="9914002001", email="note@example.org")
        session.add(donor)
        session.commit()

        response = client.patch(
            f"/api/donors/{donor.id}/status",
            headers=admin_headers(client),
            json={"status": "available", "note": "Nonsense"},
        )
        assert response.status_code == 422

    def test_a_donor_can_set_their_own_availability(self, client, donor_account):
        response = client.patch(
            "/api/me/donor/status",
            headers=auth_header(client, "donor@example.org"),
            json={"status": "unavailable_medical", "note": "On antibiotics."},
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "unavailable_medical"

    def test_a_donor_cannot_change_another_donors_availability(
        self, client, donor_account, session
    ):
        other = make_donor(phone="9914003001", email="notyou@example.org")
        session.add(other)
        session.commit()

        response = client.patch(
            f"/api/donors/{other.id}/status",
            headers=auth_header(client, "donor@example.org"),
            json={"status": "unavailable_moved"},
        )
        assert response.status_code == 403


class TestAggregateAvailability:
    def test_every_blood_group_gets_a_row_including_zeroes(self, client, patient, session):
        """A zero is the most important number here; an absent row reads as missing data."""

        session.add(make_donor(blood_group=BloodGroup.O_NEGATIVE, phone="9915000001",
                               email="agg@example.org"))
        session.commit()

        body = client.get(
            "/api/availability", headers=auth_header(client, "patient@example.org")
        ).get_json()

        assert len(body["items"]) == 8
        by_group = {row["blood_group"]: row for row in body["items"]}
        assert by_group["O-"]["eligible_donors"] == 1
        assert by_group["AB+"]["eligible_donors"] == 0

    def test_it_carries_no_identifying_information(self, client, patient, session):
        session.add(
            make_donor(name="Private Person", phone="9915001001", email="priv@example.org")
        )
        session.commit()

        raw = client.get(
            "/api/availability", headers=auth_header(client, "patient@example.org")
        ).get_data(as_text=True)

        assert "Private Person" not in raw
        assert "9915001001" not in raw
        assert "priv@example.org" not in raw
