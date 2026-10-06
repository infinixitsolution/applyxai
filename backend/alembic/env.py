import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.core.database import build_engine  # noqa: E402
from backend.app.models import Base  # noqa: E402
from backend.app.models.base import UTCDateTime  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # Tests pass an explicit URL through the Alembic Config; otherwise use the app settings.
    return config.attributes.get("database_url") or settings.DATABASE_URL


def _render_item(type_, obj, autogen_context):
    # UTCDateTime is a Python-side wrapper; the column itself is a plain timezone-aware DateTime.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _configure_kwargs(url: str) -> dict:
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "render_item": _render_item,
        # SQLite can't ALTER most things in place; batch mode recreates the table instead.
        "render_as_batch": url.startswith("sqlite"),
    }


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **_configure_kwargs(url))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    connectable = config.attributes.get("connection") or build_engine(url)
    if hasattr(connectable, "connect"):
        with connectable.connect() as connection:
            context.configure(connection=connection, **_configure_kwargs(url))
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(connection=connectable, **_configure_kwargs(url))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
