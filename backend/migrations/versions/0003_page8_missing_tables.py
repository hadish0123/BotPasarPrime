"""Page 8 migration compatibility marker.

The canonical ORM schema is already created by 0001_initial. Earlier versions
of this file attempted to create duplicate legacy ``bots`` and ``user_roles``
tables that are not part of the production model. Keeping this revision as a
no-op preserves the migration history without creating divergent schemas.
"""

revision = "0003_page8_missing_tables"
down_revision = "0002_page8_data_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
