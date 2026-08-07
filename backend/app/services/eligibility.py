"""Who is medically able to give blood right now.

This module owns the eligibility rule and is the only place it is expressed. It offers
the rule in two forms:

- ``eligibility_clause()`` returns a SQL expression, so the database can filter and
  count eligible donors without loading them.
- ``ineligibility_reasons()`` evaluates the same rule against a loaded donor and returns
  the reasons it failed, so a person can be told why rather than just excluded.

Both derive from the same thresholds. They are two renderings of one rule, not two
rules, which is the point: an eligible-donor count that disagreed with the broadcast
selector would be a silently wrong number on the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

import sqlalchemy as sa
from flask import current_app

from ..models import Donor, DonorStatus, Sex


@dataclass(frozen=True)
class EligibilityRules:
    """The configured thresholds, resolved once per call site.

    Read from configuration rather than hardcoded because the safe inter-donation
    interval is medical policy and varies by jurisdiction. A network operating under
    different guidance changes an environment variable, not the source.
    """

    cooldown_days_male: int
    cooldown_days_female: int
    min_age: int
    max_age: int
    min_weight_kg: Decimal

    @classmethod
    def from_config(cls) -> "EligibilityRules":
        cfg = current_app.config
        return cls(
            cooldown_days_male=int(cfg["COOLDOWN_DAYS_MALE"]),
            cooldown_days_female=int(cfg["COOLDOWN_DAYS_FEMALE"]),
            min_age=int(cfg["MIN_DONOR_AGE"]),
            max_age=int(cfg["MAX_DONOR_AGE"]),
            min_weight_kg=Decimal(str(cfg["MIN_DONOR_WEIGHT_KG"])),
        )

    def cooldown_days(self, sex: Sex) -> int:
        """The interval a donor of this sex must leave between whole blood donations.

        ``OTHER`` takes the longer interval. Erring towards a longer wait is the safe
        direction to be wrong in: the cost is a donation deferred, whereas the cost of
        the opposite error is a donation that should not have happened.
        """

        if sex is Sex.MALE:
            return self.cooldown_days_male
        return self.cooldown_days_female


def years_before(reference: date, years: int) -> date:
    """The same calendar date, a whole number of years earlier.

    The try/except handles 29 February, which has no counterpart in a non-leap year.
    Falling back to the 28th is the convention that keeps a birthday inside the same
    month.
    """

    try:
        return reference.replace(year=reference.year - years)
    except ValueError:
        return reference.replace(year=reference.year - years, day=28)


def calculate_age(date_of_birth: date, on: Optional[date] = None) -> int:
    """Age in completed years."""

    reference = on or date.today()
    had_birthday = (reference.month, reference.day) >= (date_of_birth.month, date_of_birth.day)
    return reference.year - date_of_birth.year - (0 if had_birthday else 1)


def eligibility_clause(
    rules: Optional[EligibilityRules] = None, on: Optional[date] = None
) -> sa.ColumnElement[bool]:
    """A SQL predicate selecting donors who may donate on ``on`` (default today).

    Every threshold is turned into a bound date or number in Python before it reaches
    SQL. Doing the calendar arithmetic here rather than with database date functions
    keeps the predicate sargable, so the composite index on
    ``(blood_group, status, last_donation_date)`` is actually used instead of the
    planner having to evaluate an expression per row.
    """

    rules = rules or EligibilityRules.from_config()
    today = on or date.today()

    # age >= min_age means the donor was born on or before this date.
    latest_birth_date = years_before(today, rules.min_age)
    # age <= max_age means the donor has not yet had their (max_age + 1)th birthday.
    earliest_birth_date = years_before(today, rules.max_age + 1) + timedelta(days=1)

    male_cutoff = today - timedelta(days=rules.cooldown_days_male)
    other_cutoff = today - timedelta(days=rules.cooldown_days_female)

    cooldown_cutoff = sa.case(
        (Donor.sex == Sex.MALE, sa.literal(male_cutoff, sa.Date)),
        else_=sa.literal(other_cutoff, sa.Date),
    )

    return sa.and_(
        Donor.status == DonorStatus.AVAILABLE,
        Donor.date_of_birth <= latest_birth_date,
        Donor.date_of_birth >= earliest_birth_date,
        Donor.weight_kg >= rules.min_weight_kg,
        # A donor who has never donated has no cooldown to have elapsed. Without the
        # NULL branch, SQL three-valued logic would silently exclude every first-time
        # donor from every broadcast.
        sa.or_(
            Donor.last_donation_date.is_(None),
            Donor.last_donation_date <= cooldown_cutoff,
        ),
    )


def next_eligible_date(donor: Donor, rules: Optional[EligibilityRules] = None) -> Optional[date]:
    """The earliest date this donor's cooldown allows another donation.

    ``None`` when there is no cooldown to serve, either because they have never donated
    or because the interval has already elapsed.
    """

    rules = rules or EligibilityRules.from_config()
    if donor.last_donation_date is None:
        return None
    ready_on = donor.last_donation_date + timedelta(days=rules.cooldown_days(donor.sex))
    return ready_on if ready_on > date.today() else None


def ineligibility_reasons(
    donor: Donor, rules: Optional[EligibilityRules] = None, on: Optional[date] = None
) -> List[str]:
    """Every reason this donor cannot currently donate, as readable sentences.

    All reasons are collected rather than returning at the first failure, so a donor is
    not told about one problem, fixes it, and then discovers a second.
    """

    rules = rules or EligibilityRules.from_config()
    today = on or date.today()
    reasons: List[str] = []

    if donor.status is not DonorStatus.AVAILABLE:
        labels = {
            DonorStatus.UNAVAILABLE_MOVED: "Marked unavailable after moving away.",
            DonorStatus.UNAVAILABLE_TRAVELING: "Marked unavailable while travelling.",
            DonorStatus.UNAVAILABLE_MEDICAL: "Marked medically unable to donate.",
        }
        reasons.append(labels.get(donor.status, "Marked unavailable."))

    age = calculate_age(donor.date_of_birth, today)
    if age < rules.min_age:
        reasons.append(f"Below the minimum donation age of {rules.min_age}.")
    elif age > rules.max_age:
        reasons.append(f"Above the maximum donation age of {rules.max_age}.")

    if donor.weight_kg < rules.min_weight_kg:
        reasons.append(f"Below the minimum donation weight of {rules.min_weight_kg} kg.")

    ready_on = next_eligible_date(donor, rules)
    if ready_on is not None:
        reasons.append(
            f"Within the {rules.cooldown_days(donor.sex)} day interval since the last "
            f"donation. Eligible again on {ready_on.isoformat()}."
        )

    return reasons


def is_eligible(
    donor: Donor, rules: Optional[EligibilityRules] = None, on: Optional[date] = None
) -> bool:
    return not ineligibility_reasons(donor, rules, on)
