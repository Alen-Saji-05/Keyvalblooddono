"""Application configuration.

Plain classes read from the environment, rather than a settings library. Flask already
has a configuration object and expects extension settings to live in it under specific
keys, so introducing a parallel settings model would mean maintaining a mapping between
the two. The validation that matters here - that secrets are present outside
development - is a handful of explicit checks.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import List


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _list(name: str, default: str = "") -> List[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class BaseConfig:
    """Settings common to every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "development-secret-do-not-use-in-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/bloodnet"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Verifies a pooled connection before handing it out. Without this, a connection
        # dropped by the server or an intermediary surfaces as an error on a random
        # request some time later, which is a difficult failure to diagnose.
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    # --- JWT ---
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=_int("JWT_ACCESS_TOKEN_EXPIRES", 900))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=_int("JWT_REFRESH_TOKEN_EXPIRES", 604800))

    # The access token is returned in the response body and held in browser memory. The
    # refresh token is delivered only as a cookie, so the two live in different places
    # and a script that can read one cannot read the other.
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_ACCESS_COOKIE_NAME = "bloodnet_access"
    JWT_REFRESH_COOKIE_NAME = "bloodnet_refresh"
    # Scoped to the auth namespace rather than to /api/auth/refresh alone. Logout has to
    # revoke the refresh token, so it needs to receive it; a cookie scoped to the refresh
    # path only is simply never sent to the logout endpoint, which makes signing out
    # impossible. /api/auth is still narrow enough that the bulk of API traffic - donors,
    # requests, donations, summary - never carries this credential.
    JWT_REFRESH_COOKIE_PATH = "/api/auth"
    JWT_COOKIE_SECURE = _bool("JWT_COOKIE_SECURE", False)
    JWT_COOKIE_SAMESITE = "Strict"
    # SameSite=Strict already blocks the cross-site request that CSRF depends on, and the
    # refresh cookie is the only cookie carrying a credential.
    JWT_COOKIE_CSRF_PROTECT = False

    # How long a rotated refresh token keeps working after being superseded.
    #
    # Rotation revokes the presented token, which is what limits a stolen one to a single
    # use. Applied with no leeway it also breaks legitimate use: two browser tabs that
    # refresh at the same moment both send the same cookie, the first rotation revokes it,
    # and the second request - already in flight - is rejected and signs the user out.
    #
    # A short grace window keeps the security property, since a thief still has to use the
    # token within seconds of the real user's rotation, while tolerating the race. This is
    # the same leeway approach used by mainstream identity providers.
    JWT_REFRESH_REUSE_GRACE_SECONDS = _int("JWT_REFRESH_REUSE_GRACE_SECONDS", 20)

    # --- CORS ---
    CORS_ORIGINS = _list("CORS_ORIGINS", "http://localhost:5173")

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_LOGIN = os.environ.get("RATELIMIT_LOGIN", "10 per minute")

    # --- Notifications ---
    NOTIFIER_DRIVER = os.environ.get("NOTIFIER_DRIVER", "console")
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = _int("SMTP_PORT", 587)
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "bloodnet@example.org")
    SMTP_USE_TLS = _bool("SMTP_USE_TLS", True)

    # --- Eligibility rules ---
    # Whole blood inter-donation intervals. Configuration rather than constants because
    # the safe interval is a medical policy that varies by jurisdiction, and a network
    # operating under different guidance should not need a code change.
    COOLDOWN_DAYS_MALE = _int("COOLDOWN_DAYS_MALE", 90)
    COOLDOWN_DAYS_FEMALE = _int("COOLDOWN_DAYS_FEMALE", 120)
    MIN_DONOR_AGE = _int("MIN_DONOR_AGE", 18)
    MAX_DONOR_AGE = _int("MAX_DONOR_AGE", 65)
    MIN_DONOR_WEIGHT_KG = _int("MIN_DONOR_WEIGHT_KG", 45)

    # --- Initial administrator, consumed by the seed-admin command ---
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    ADMIN_NAME = os.environ.get("ADMIN_NAME", "Network Administrator")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/bloodnet_test"
    )
    # Rate limiting would otherwise make a test that logs in repeatedly fail for reasons
    # unrelated to what it is testing.
    RATELIMIT_ENABLED = False
    NOTIFIER_DRIVER = "null"


class ProductionConfig(BaseConfig):
    DEBUG = False
    JWT_COOKIE_SECURE = True

    def __init__(self) -> None:
        # Checked at construction rather than import, so that merely importing the module
        # in a development shell does not fail.
        missing = [
            name
            for name in ("SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                "Refusing to start in production without: " + ", ".join(missing)
            )


CONFIGURATIONS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def resolve_config(name: str | None = None):
    """Pick a configuration class by name, defaulting to development."""

    key = (name or os.environ.get("FLASK_ENV") or "development").lower()
    return CONFIGURATIONS.get(key, DevelopmentConfig)
