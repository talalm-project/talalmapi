from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.environment import load_environment
from app.db import Base, db

load_environment()

from config import Config  # noqa: E402
from app.models import (  # noqa: F401,E402
    compile_job,
    connector,
    embedding_config,
    notebook,
    notebook_file,
    notebook_note,
    notebook_vector,
    paper,
    paper_file,
    user,
)


config = context.config
config.set_main_option("sqlalchemy.url", Config.SQLALCHEMY_DATABASE_URI)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db.configure(Config.SQLALCHEMY_DATABASE_URI)
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
