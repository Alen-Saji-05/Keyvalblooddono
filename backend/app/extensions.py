"""Flask extension instances.

Declared in their own module, unbound to any application, so that the application
factory can create several independent applications - one per test, for example -
without extensions carrying state between them.
"""

from __future__ import annotations

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
