"""Shared pytest fixtures.

Tests run against a real PostgreSQL database, not SQLite. The logic worth testing here -
the fulfilment recomputation under a row lock, the eligibility predicate, the enum
columns, the check constraints - is expressed in SQL that SQLite either implements
differently or does not implement at all, so testing against it would test the wrong
thing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from flask_migrate import upgrade as alembic_upgrade

from app import create_app
from app.extensions import db as _db
from app.models import BloodGroup, Donor, DonorStatus, Sex, User, UserRole
from app.security.passwords import hash_password

TEST_PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        # The schema is built by running the real migration rather than by
        # metadata.create_all. create_all would not work anyway - the enum types are
        # declared with create_type=False so that the migration owns them - but the more
        # important reason is that this exercises the migration on every test run, so a
        # revision that does not match the models fails here rather than in production.
        _db.session.execute(sa.text("DROP SCHEMA public CASCADE"))
        _db.session.execute(sa.text("CREATE SCHEMA public"))
        _db.session.commit()
        alembic_upgrade()
        yield application


@pytest.fixture(autouse=True)
def clean_tables(app):
    """Empty every table between tests.

    Truncation rather than a rolled-back transaction, because the endpoints under test
    commit. Wrapping each test in a transaction the endpoint then commits would need
    savepoint gymnastics that are easy to get subtly wrong, and a wrong isolation fixture
    produces tests that pass because of leaked state.

    RESTART IDENTITY keeps generated ids predictable across tests; CASCADE handles the
    foreign keys so the tables need no ordering.
    """

    yield
    tables = ", ".join(
        f'"{name}"' for name in _db.metadata.tables if name != "alembic_version"
    )
    _db.session.execute(sa.text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    _db.session.commit()
    # Discard the session along with its identity map. Truncating leaves the previous
    # test's objects cached under primary keys that RESTART IDENTITY has just handed back
    # out, so the next test's fixtures collide with stale instances for the same id.
    _db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session(app):
    return _db.session


def make_donor(**overrides) -> Donor:
    """A donor who is eligible unless a test overrides something to make them not."""

    defaults = dict(
        name="Test Donor",
        blood_group=BloodGroup.O_NEGATIVE,
        sex=Sex.MALE,
        date_of_birth=date.today() - timedelta(days=30 * 365),
        weight_kg=Decimal("70.00"),
        phone="9900000001",
        email="test.donor@example.org",
        place="Kochi",
        last_donation_date=None,
        status=DonorStatus.AVAILABLE,
    )
    defaults.update(overrides)
    return Donor(**defaults)


def make_user(role: UserRole, email: str, donor_id=None, **overrides) -> User:
    defaults = dict(
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
        full_name="Test Person",
        role=role,
        donor_id=donor_id,
    )
    defaults.update(overrides)
    return User(**defaults)


@pytest.fixture
def admin(session) -> User:
    user = make_user(UserRole.ADMIN, "admin@example.org")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def patient(session) -> User:
    user = make_user(UserRole.PATIENT, "patient@example.org")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def donor_account(session):
    """A donor record with a linked login, returned as a (donor, user) pair."""

    donor = make_donor()
    session.add(donor)
    session.flush()
    user = make_user(UserRole.DONOR, "donor@example.org", donor_id=donor.id)
    session.add(user)
    session.commit()
    return donor, user


def login(client, email: str, password: str = TEST_PASSWORD):
    """Sign in and return the response, leaving the refresh cookie in the client jar."""

    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth_header(client, email: str, password: str = TEST_PASSWORD) -> dict:
    response = login(client, email, password)
    assert response.status_code == 200, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}
