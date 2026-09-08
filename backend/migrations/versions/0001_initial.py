"""3XSHOP initial schema"""
from alembic import op
import sqlalchemy as sa
from app.models.entities import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    Base.metadata.drop_all(op.get_bind())
