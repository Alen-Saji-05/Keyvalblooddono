"""Reusable field validators and the password policy."""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..api.errors import UnprocessableEntity

# Minimum length only, with no composition rules. This follows current NIST guidance
# (SP 800-63B), which found that mandatory character-class rules and forced rotation push
# people towards predictable substitutions and reuse, while length is what actually
# resists guessing. Twelve applies to every role, including administrators.
MIN_PASSWORD_LENGTH = 12

# A very small screen against the passwords that dominate credential-stuffing lists. Not
# a substitute for a real breach corpus - a production deployment should check against
# one - but it costs nothing and stops the worst choices. Recorded as a known gap in
# explainer.md.
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "passw0rd",
    "123456789012",
    "qwertyuiop",
    "administrator",
    "letmein12345",
    "iloveyou1234",
    "welcome12345",
    "blooddonation",
    "bloodbank123",
}

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s\-]{6,19}$")


def validate_password(password: str, *, email: Optional[str] = None) -> str:
    """Apply the password policy, raising a 422 with a usable message on failure."""

    if len(password) < MIN_PASSWORD_LENGTH:
        raise UnprocessableEntity(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            details={"fields": {"password": [f"Use at least {MIN_PASSWORD_LENGTH} characters."]}},
        )

    lowered = password.lower()

    if lowered in COMMON_PASSWORDS:
        raise UnprocessableEntity(
            "That password is too common.",
            details={"fields": {"password": ["Choose something less predictable."]}},
        )

    # A password built from the address it protects is disclosed by the username.
    if email:
        local_part = email.split("@", 1)[0].lower()
        if len(local_part) >= 4 and local_part in lowered:
            raise UnprocessableEntity(
                "Password must not contain your email address.",
                details={"fields": {"password": ["Do not reuse your email address."]}},
            )

    return password


def validate_phone(value: str) -> str:
    """Accept an optional leading plus, then digits with spaces or hyphens.

    Deliberately permissive. This network operates across regions and a strict national
    format would reject numbers that are perfectly reachable. The check exists to catch
    a field filled with something that is plainly not a phone number, not to normalise.
    """

    if not PHONE_PATTERN.match(value):
        raise ValueError("Enter a valid phone number.")
    return value


def validate_past_date(value: date) -> date:
    if value > date.today():
        raise ValueError("Date cannot be in the future.")
    return value


def validate_not_past_date(value: date) -> date:
    if value < date.today():
        raise ValueError("Date cannot be in the past.")
    return value
