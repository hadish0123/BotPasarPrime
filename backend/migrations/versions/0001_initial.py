"""3XSHOP initial schema.

The initial migration creates the complete ORM schema from a clean database.
Later migrations only add indexes or compatibility structures.
"""

from alembic import op

from app.models.entities import Base
from app.models.onboarding import OnboardingPayment  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
