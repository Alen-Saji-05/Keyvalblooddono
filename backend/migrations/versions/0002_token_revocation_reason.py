"""Record why a refresh token was revoked

Revision ID: 0002_revocation_reason
Revises: 0001_initial
Create Date: 2026-08-07

Refresh tokens rotate, so every refresh blocklists the client's own previous token. With
no leeway that breaks legitimate use: two tabs, or a page restoring its session while a
query retries, both send the same cookie, the first rotation revokes it, and the second
request is rejected and signs the user out.

The fix is a short grace period on reuse - but only for tokens superseded by rotation. A
token revoked by logout must stop working immediately, because that is exactly what the
logout button promises. Telling the two apart requires storing the reason.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_revocation_reason"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

REVOCATION_REASONS = ("rotated", "logout")


def upgrade():
    bind = op.get_bind()
    postgresql.ENUM(*REVOCATION_REASONS, name="revocation_reason").create(
        bind, checkfirst=False
    )

    op.add_column(
        "token_blocklist",
        sa.Column(
            "reason",
            postgresql.ENUM(name="revocation_reason", create_type=False),
            nullable=False,
            # Existing rows predate the distinction. They are defaulted to 'rotated',
            # which is the more permissive of the two, but every one of them is a
            # already-expired or soon-to-expire token from before this deployment, so the
            # grace period cannot resurrect a session that mattered.
            server_default="rotated",
        ),
    )


def downgrade():
    op.drop_column("token_blocklist", "reason")
    postgresql.ENUM(name="revocation_reason").drop(op.get_bind(), checkfirst=False)
