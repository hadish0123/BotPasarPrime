from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

import app.models.onboarding  # noqa: F401


def test_migration_chain_has_single_root_and_current_head() -> None:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    revisions = list(scripts.walk_revisions())
    roots = [revision for revision in revisions if revision.down_revision is None]
    heads = scripts.get_heads()

    assert [revision.revision for revision in roots] == ["0001_initial"]
    assert heads == ["0012_seed_rbac_permissions"]
