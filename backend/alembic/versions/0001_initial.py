"""Initial 3XSHOP schema.

The initial revision creates the schema from the SQLAlchemy metadata so a clean
PostgreSQL deployment and all subsequent additive revisions share one source of
truth. Later revisions remain explicit and rollbackable.
"""

from alembic import op

from app.core.db import Base
from app.models import entities, onboarding  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
