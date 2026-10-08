"""The schema is made only by migrations, and they match the code's schema:
upgrade, compare with gnosis/data/schema.py (no difference allowed), go all
the way down and up again; the built-in roles are seeded."""
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select

from gnosis.data import schema


def test_the_migrated_database_matches_the_schema_in_code(engine):
    with engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), schema.metadata)
    assert diff == [], diff


def test_migrations_go_down_and_up_again(alembic_config, engine):
    command.downgrade(alembic_config, "base")
    with engine.connect() as c:
        tables = c.exec_driver_sql("select count(*) from information_schema.tables "
                                   "where table_schema = 'public' and table_name != 'alembic_version'").scalar()
    assert tables == 0
    command.upgrade(alembic_config, "head")
    test_the_migrated_database_matches_the_schema_in_code(engine)


def test_built_in_roles_and_permissions_are_seeded(conn):
    roles = dict(conn.execute(select(schema.roles.c.name, schema.roles.c.builtin)).all())
    assert set(roles) == set(schema.BUILTIN_ROLES) and all(roles.values())
    perms = set(conn.execute(select(schema.permissions.c.name)).scalars())
    assert perms == set(schema.BUILTIN_PERMISSIONS)
    grants = {}
    for role, perm in conn.execute(select(schema.role_permissions.c.role, schema.role_permissions.c.permission)):
        grants.setdefault(role, set()).add(perm)
    assert grants == {r: set(p) for r, p in schema.ROLE_GRANTS.items() if p}, "the migration seeds what the code says"
