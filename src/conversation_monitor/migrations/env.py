from alembic import context
from sqlalchemy import Connection

connection: Connection | None = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError(
        "Migrations run through conversation_monitor.database.initialize_database, "
        "which the application calls at startup. Use alembic to list revisions"
    )

context.configure(connection=connection)
with context.begin_transaction():
    context.run_migrations()
