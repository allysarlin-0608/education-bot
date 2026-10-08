"""Alembic: runs the migrations in versions/ against GNOSIS_DATABASE_URL."""
from alembic import context
from sqlalchemy import create_engine

from gnosis.data.schema import metadata
from gnosis.infra.config import settings

config = context.config
url = config.attributes.get("url") or settings().database_url.get_secret_value()


def run() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
