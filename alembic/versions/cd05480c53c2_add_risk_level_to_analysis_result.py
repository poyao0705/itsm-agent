"""add risk_level to analysis_result

Revision ID: cd05480c53c2
Revises: 6bf4a4ed2b7b
Create Date: 2026-02-06 11:40:38.904430

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cd05480c53c2"
down_revision: Union[str, Sequence[str], None] = "6bf4a4ed2b7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "analysis_result",
        sa.Column("risk_level", sa.String(), nullable=False, server_default="LOW"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("analysis_result", "risk_level")
