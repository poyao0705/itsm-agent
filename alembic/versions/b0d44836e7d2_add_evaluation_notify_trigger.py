"""add_evaluation_notify_trigger

Revision ID: b0d44836e7d2
Revises: 5f0b7f3e6d62
Create Date: 2026-02-07 01:31:32.101432

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b0d44836e7d2"
down_revision: Union[str, Sequence[str], None] = "5f0b7f3e6d62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the notification function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_evaluation_change()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('eval_updates', '');
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # Create the trigger
    op.execute(
        """
        CREATE TRIGGER evaluation_run_changed
        AFTER INSERT OR UPDATE OR DELETE ON evaluation_run
        FOR EACH ROW EXECUTE FUNCTION notify_evaluation_change();
    """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS evaluation_run_changed ON evaluation_run;")
    op.execute("DROP FUNCTION IF EXISTS notify_evaluation_change();")
