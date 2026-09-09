"""3XSHOP initial schema.

The initial migration creates the complete canonical ORM entity schema from a
clean database. Dedicated feature migrations own tables introduced later so
fresh installs and upgrades follow the same deterministic revision chain.
"""

from alembic import op

from app.models.entities import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
