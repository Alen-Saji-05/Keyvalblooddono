"""Command line commands registered on the Flask application."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import click
import sqlalchemy as sa
from flask import Flask
from flask.cli import with_appcontext

from .extensions import db
from .models import (
    BloodGroup,
    BloodRequest,
    Donation,
    Donor,
    DonorStatus,
    Notification,
    RequestStatus,
    Sex,
    User,
    UserRole,
)
from .security import hash_password


def register_commands(app: Flask) -> None:
    app.cli.add_command(seed_admin)
    app.cli.add_command(seed_demo)
    app.cli.add_command(purge_expired_tokens)


@click.command("seed-admin")
@with_appcontext
def seed_admin() -> None:
    """Create the first administrator from ADMIN_EMAIL and ADMIN_PASSWORD.

    There is no public sign-up for the admin role, because an admin can read every
    donor's contact details and medical reason for unavailability. This command is how
    the first such account comes into existence; every later one is created by an
    existing admin.
    """

    from flask import current_app

    email = (current_app.config.get("ADMIN_EMAIL") or "").strip().lower()
    password = current_app.config.get("ADMIN_PASSWORD") or ""
    name = current_app.config.get("ADMIN_NAME") or "Network Administrator"

    if not email or not password:
        raise click.ClickException(
            "ADMIN_EMAIL and ADMIN_PASSWORD must be set in the environment or .env file."
        )
    if len(password) < 12:
        raise click.ClickException(
            "ADMIN_PASSWORD must be at least 12 characters. This account can read every "
            "donor record in the system."
        )

    existing = db.session.scalar(sa.select(User).where(User.email == email))
    if existing is not None:
        click.echo(f"An account already exists for {email}. Nothing to do.")
        return

    db.session.add(
        User(
            email=email,
            password_hash=hash_password(password),
            full_name=name,
            role=UserRole.ADMIN,
        )
    )
    db.session.commit()
    click.echo(f"Created administrator {email}.")


@click.command("purge-expired-tokens")
@with_appcontext
def purge_expired_tokens() -> None:
    """Delete blocklist rows for tokens that have expired anyway.

    A revoked token stops mattering once its own expiry passes, so the row exists only
    until then. Without this the table grows by one row per logout, forever.
    """

    from .models import TokenBlocklist

    deleted = db.session.execute(
        sa.delete(TokenBlocklist).where(TokenBlocklist.expires_at < sa.func.now())
    ).rowcount
    db.session.commit()
    click.echo(f"Removed {deleted} expired blocklist entries.")


@click.command("seed-demo")
@click.option(
    "--force",
    is_flag=True,
    help="Seed even if donors already exist. Existing rows are left untouched.",
)
@with_appcontext
def seed_demo(force: bool) -> None:
    """Load a demonstration dataset.

    The dataset is built relative to today rather than around fixed dates, so that the
    eligibility rules produce a meaningful spread whenever it is run: some donors are
    inside their cooldown window, some are outside it, and some have never donated. A
    fixture pinned to absolute dates would have every donor eligible after a few months
    and stop exercising the rule.
    """

    if not force and db.session.scalar(sa.select(sa.func.count()).select_from(Donor)):
        raise click.ClickException(
            "The donors table is not empty. Re-run with --force to seed anyway."
        )

    today = date.today()

    def born(years: int) -> date:
        return today - timedelta(days=years * 365 + years // 4)

    donor_rows = [
        # name, group, sex, age, weight, phone, place, days since last donation
        ("Ananya Rao", BloodGroup.O_NEGATIVE, Sex.FEMALE, 29, "58.0", "9800000001", "Kochi", 200),
        ("Rahul Menon", BloodGroup.O_NEGATIVE, Sex.MALE, 34, "72.5", "9800000002", "Kochi", 120),
        ("Farhan Qureshi", BloodGroup.O_NEGATIVE, Sex.MALE, 41, "80.0", "9800000003", "Thrissur", 20),
        ("Meera Nair", BloodGroup.O_POSITIVE, Sex.FEMALE, 26, "55.0", "9800000004", "Kochi", None),
        ("Vikram Iyer", BloodGroup.O_POSITIVE, Sex.MALE, 38, "78.0", "9800000005", "Kozhikode", 95),
        ("Sneha Pillai", BloodGroup.A_POSITIVE, Sex.FEMALE, 31, "60.0", "9800000006", "Kochi", 400),
        ("Arjun Das", BloodGroup.A_POSITIVE, Sex.MALE, 45, "85.0", "9800000007", "Thrissur", 45),
        ("Kavya Krishnan", BloodGroup.A_NEGATIVE, Sex.FEMALE, 23, "51.0", "9800000008", "Kochi", None),
        ("Joseph Thomas", BloodGroup.B_POSITIVE, Sex.MALE, 52, "76.0", "9800000009", "Kottayam", 150),
        ("Divya Suresh", BloodGroup.B_POSITIVE, Sex.FEMALE, 28, "49.0", "9800000010", "Kochi", 300),
        ("Nikhil Varma", BloodGroup.B_NEGATIVE, Sex.MALE, 36, "70.0", "9800000011", "Kozhikode", None),
        ("Aisha Beevi", BloodGroup.AB_POSITIVE, Sex.FEMALE, 33, "57.0", "9800000012", "Kollam", 180),
        ("Sanjay Kurup", BloodGroup.AB_NEGATIVE, Sex.MALE, 47, "82.0", "9800000013", "Kochi", 60),
        # Deliberately ineligible cases, so the eligibility rule has something to exclude:
        # below the minimum weight, and above the maximum age.
        ("Ravi Chandran", BloodGroup.O_POSITIVE, Sex.MALE, 30, "42.0", "9800000014", "Thrissur", None),
        ("Leela Amma", BloodGroup.A_POSITIVE, Sex.FEMALE, 71, "62.0", "9800000015", "Kottayam", None),
    ]

    donors: list[Donor] = []
    for name, group, sex, age, weight, phone, place, since in donor_rows:
        donors.append(
            Donor(
                name=name,
                blood_group=group,
                sex=sex,
                date_of_birth=born(age),
                weight_kg=Decimal(weight),
                phone=phone,
                email=f"{name.split()[0].lower()}.{phone[-4:]}@example.org",
                place=place,
                last_donation_date=None if since is None else today - timedelta(days=since),
                status=DonorStatus.AVAILABLE,
            )
        )

    # Two donors marked unavailable for different reasons, so the status filter and the
    # broadcast exclusion have real rows to act on.
    donors[4].status = DonorStatus.UNAVAILABLE_TRAVELING
    donors[4].status_note = "Working overseas until the end of the year."
    donors[8].status = DonorStatus.UNAVAILABLE_MEDICAL
    donors[8].status_note = "Advised to wait following a course of antibiotics."

    db.session.add_all(donors)
    db.session.flush()

    patient = User(
        email="patient@example.org",
        password_hash=hash_password("demo-patient-password"),
        full_name="Sunil Joseph",
        role=UserRole.PATIENT,
    )
    donor_user = User(
        email="donor@example.org",
        password_hash=hash_password("demo-donor-password"),
        full_name=donors[0].name,
        role=UserRole.DONOR,
        donor_id=donors[0].id,
    )
    db.session.add_all([patient, donor_user])
    db.session.flush()

    # An open request nobody has answered yet, a partially fulfilled one, and a fully
    # fulfilled one, so every branch of the status derivation is represented.
    open_request = BloodRequest(
        created_by_user_id=patient.id,
        patient_name="Sunil Joseph",
        blood_group=BloodGroup.O_NEGATIVE,
        hospital="Lakeside General Hospital",
        place="Kochi",
        contact_phone="9800001111",
        units_required=3,
        needed_by_date=today + timedelta(days=5),
        status=RequestStatus.OPEN,
        notes="Scheduled surgery. Units needed before the operating date.",
    )
    partial_request = BloodRequest(
        created_by_user_id=patient.id,
        patient_name="Grace Mathew",
        blood_group=BloodGroup.A_POSITIVE,
        hospital="Riverside Medical Centre",
        place="Thrissur",
        contact_phone="9800002222",
        units_required=4,
        needed_by_date=today + timedelta(days=2),
        status=RequestStatus.OPEN,
    )
    fulfilled_request = BloodRequest(
        patient_name="Ibrahim Kutty",
        blood_group=BloodGroup.B_POSITIVE,
        hospital="Central City Hospital",
        place="Kottayam",
        contact_phone="9800003333",
        units_required=2,
        needed_by_date=today - timedelta(days=3),
        status=RequestStatus.OPEN,
    )
    db.session.add_all([open_request, partial_request, fulfilled_request])
    db.session.flush()

    # Notifications, some answered and some not, so the response rate is not a
    # degenerate 0 or 100 per cent.
    now = sa.func.now()
    notified = [
        (donors[0], open_request, False),
        (donors[1], open_request, True),
        (donors[2], open_request, False),
        (donors[5], partial_request, True),
        (donors[6], partial_request, False),
        (donors[8], fulfilled_request, True),
        (donors[9], fulfilled_request, True),
    ]
    for donor, request, responded in notified:
        db.session.add(
            Notification(
                donor_id=donor.id,
                request_id=request.id,
                responded=responded,
                response_at=now if responded else None,
            )
        )

    # Donations. The partially fulfilled request receives one unit of the four it needs;
    # the fulfilled request receives its two units from two different people, which is
    # the multi-donor case the whole fulfilment design exists for.
    donation_rows = [
        (donors[5], partial_request, 1, today - timedelta(days=1)),
        (donors[8], fulfilled_request, 1, today - timedelta(days=6)),
        (donors[9], fulfilled_request, 1, today - timedelta(days=5)),
    ]
    for donor, request, units, when in donation_rows:
        db.session.add(
            Donation(
                donor_id=donor.id,
                request_id=request.id,
                units_given=units,
                donation_date=when,
            )
        )

    # Fulfilment totals are recomputed from the donations just inserted rather than
    # written by hand, so the seed exercises the same code path the API uses and cannot
    # produce a dataset the status check constraint would reject.
    db.session.flush()
    from .services.fulfilment import recompute_request_fulfilment

    for request in (open_request, partial_request, fulfilled_request):
        recompute_request_fulfilment(db.session, request.id)

    db.session.commit()

    click.echo(
        f"Seeded {len(donors)} donors, 3 requests, {len(donation_rows)} donations, "
        f"{len(notified)} notifications, and 2 demonstration accounts."
    )
    click.echo("  patient@example.org / demo-patient-password")
    click.echo("  donor@example.org / demo-donor-password")
