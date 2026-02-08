"""remove_pg_notify_trigger

Revision ID: 98d381fc7074
Revises: 4d9e1c0a276c
Create Date: 2026-02-09 00:22:53.817940

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "98d381fc7074"
down_revision: Union[str, Sequence[str], None] = "4d9e1c0a276c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - remove pg_notify trigger."""
    op.execute("DROP TRIGGER IF EXISTS evaluation_run_changed ON evaluation_run;")
    op.execute("DROP FUNCTION IF EXISTS notify_evaluation_change();")


def downgrade() -> None:
    """Downgrade schema - restore pg_notify trigger."""
    # Create the notification function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_evaluation_change()
        RETURNS trigger AS $$
        DECLARE
            payload text;
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                payload = OLD.id::text;
            ELSE
                payload = NEW.id::text;
            END IF;
            PERFORM pg_notify('eval_updates', payload);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    op.execute(
        """
        CREATE TRIGGER evaluation_run_changed
        AFTER INSERT OR UPDATE OR DELETE ON evaluation_run
        FOR EACH ROW EXECUTE FUNCTION notify_evaluation_change();
    """
    )
