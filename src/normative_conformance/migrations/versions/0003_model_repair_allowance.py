from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"


def upgrade() -> None:
    """Store the existing repair policy as a duration on each immutable model."""
    op.execute("""
        ALTER TABLE normative_model_version ADD COLUMN repair_allowance_us INTEGER
        CHECK (repair_allowance_us IS NULL OR (type = 'undesired' AND repair_allowance_us > 0))
    """)
    op.execute("DROP TRIGGER model_no_update")
    op.execute("""
        UPDATE normative_model_version SET repair_allowance_us = 10000000 WHERE repairable = 1
    """)
    op.execute("""
        CREATE TRIGGER model_no_update BEFORE UPDATE ON normative_model_version
        BEGIN SELECT RAISE(ABORT, 'model version is immutable'); END
    """)
    op.execute("ALTER TABLE normative_model_version DROP COLUMN repairable")


def downgrade() -> None:
    raise NotImplementedError("The previous model schema cannot retain custom repair allowances")
