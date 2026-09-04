"""Alembic schema-migration repo on the uv language root.

Postgres/live migrate is not a verification gate. Tests use SQLite.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    add_pinned_pytest,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)

ALEMBIC_PIN = "1.14.1"
SQLALCHEMY_PIN = "2.0.38"


def _render_env() -> str:
    return '''from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''


def _render_revision() -> str:
    return '''from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_scaffold"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scaffold_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=64), nullable=False),
    )
    op.execute("INSERT INTO scaffold_status (status) VALUES ('schema migration scaffold ready')")


def downgrade() -> None:
    op.drop_table("scaffold_status")
'''


def _render_alembic_ini() -> str:
    return """[alembic]
script_location = migrations
sqlalchemy.url = sqlite:///./scaffold.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
"""


def _render_script_py() -> str:
    return '''from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


def run_migrations_offline() -> None:
    raise RuntimeError("use env.py")
'''


def _render_init() -> str:
    return '''from __future__ import annotations

from .migrations import next_revision

__version__ = "0.1.0"


def scaffold_status() -> str:
    return "schema migration scaffold ready"
'''


def _render_migrations() -> str:
    return '''from __future__ import annotations


def next_revision(revisions: list[str], current: str | None = None) -> str | None:
    """真实可运行的迁移示例：从已应用修订前进到下一个修订。"""
    if current is None:
        return revisions[0] if revisions else None
    try:
        index = revisions.index(current)
    except ValueError:
        return None
    if index + 1 < len(revisions):
        return revisions[index + 1]
    return None
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text

from {package_name} import scaffold_status


class SmokeTest(unittest.TestCase):
    def test_sqlite_upgrade_creates_status_row(self) -> None:
        root = Path(__file__).resolve().parents[1]
        db = root / "scaffold.db"
        if db.exists():
            db.unlink()
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "migrations"))
        cfg.set_main_option("sqlalchemy.url", "sqlite:///./scaffold.db")
        command.upgrade(cfg, "head")
        engine = create_engine("sqlite:///./scaffold.db")
        with engine.connect() as connection:
            value = connection.execute(text("select status from scaffold_status")).scalar_one()
        self.assertEqual(value, "schema migration scaffold ready")
        self.assertEqual(scaffold_status(), "schema migration scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.migrations import next_revision


class DemoTest(unittest.TestCase):
    def test_next_revision_from_start(self) -> None:
        self.assertEqual(next_revision(["0001", "0002"]), "0001")

    def test_next_revision_advances(self) -> None:
        self.assertEqual(next_revision(["0001", "0002"], "0001"), "0002")

    def test_next_revision_at_head_returns_none(self) -> None:
        self.assertIsNone(next_revision(["0001", "0002"], "0002"))

    def test_next_revision_unknown_current(self) -> None:
        self.assertIsNone(next_revision(["0001"], "zzz"))


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_alembic(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-alembic":
        raise RecipeError(f"Unsupported Alembic scaffold recipe: {recipe}")
    package_name = _python_package_name(project_name)
    scaffold = run_command(
        [
            provider.executable,
            "init",
            "--lib",
            "--package",
            "--name",
            project_name,
            "--vcs",
            "none",
            "--no-pin-python",
            "--no-workspace",
            str(project_root),
        ],
        staging_root,
    )
    _patch_python_pyproject(project_root / "pyproject.toml", purpose)
    run_command(
        [provider.executable, "add", f"alembic=={ALEMBIC_PIN}", f"sqlalchemy=={SQLALCHEMY_PIN}"],
        project_root,
        timeout=600,
    )
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text(_render_init(), encoding="utf-8")
    (package_dir / "migrations.py").write_text(_render_migrations(), encoding="utf-8")
    (project_root / "alembic.ini").write_text(_render_alembic_ini(), encoding="utf-8")
    migrations = project_root / "migrations"
    versions = migrations / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (migrations / "env.py").write_text(_render_env(), encoding="utf-8")
    (migrations / "script.py.mako").write_text(
        '"""${message}"""\nfrom alembic import op\nimport sqlalchemy as sa\n${imports if imports else ""}\n'
        "revision = ${repr(up_revision)}\ndown_revision = ${repr(down_revision)}\n",
        encoding="utf-8",
    )
    (versions / "0001_scaffold.py").write_text(_render_revision(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "migrations": "migrations/",
            "config": "alembic.ini",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
