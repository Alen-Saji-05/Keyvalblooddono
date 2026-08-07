"""Flask extension instances.

Declared in their own module, unbound to any application, so that the application
factory can create several independent applications - one per test, for example -
without extensions carrying state between them.
"""

from __future__ import annotations

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from .models.base import Base

# Flask-SQLAlchemy is used for its request-scoped session handling and its binding of
# engine configuration to app config. The alternative, managing a scoped_session by
# hand, means writing teardown handlers that must not be forgotten; a leaked session
# holds a connection and, worse, an open transaction.
#
# The declarative base is our own rather than the one Flask-SQLAlchemy generates, so the
# models stay plain SQLAlchemy 2.0 classes that can be imported and unit tested without
# an application context.
db = SQLAlchemy(model_class=Base)

migrate = Migrate()

jwt = JWTManager()

# Keyed on the client address. This is the honest limit available without accounts, and
# it is applied to login and registration, which are reachable before anyone is
# authenticated. It is imperfect behind a shared NAT or a proxy that does not set
# forwarding headers, but the alternative - no limit at all - leaves an Argon2
# verification endpoint open to unlimited attempts.
limiter = Limiter(key_func=get_remote_address)

cors = CORS()
