"""convert risk_level enum to varchar

Revision ID: 6bf4a4ed2b7b
Revises: 31e74ef5e9d4
Create Date: 2026-02-06 11:26:03.571858

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6bf4a4ed2b7b"
down_revision: Union[str, Sequence[str], None] = "31e74ef5e9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Convert Enum column to VARCHAR
    op.alter_column(
        "evaluation_run",
        "risk_level",
        existing_type=sa.Enum("LOW", "HIGH", "UNKNOWN", name="risklevel"),
        type_=sa.String(),
        existing_nullable=False,
        postgresql_using="risk_level::text",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Convert VARCHAR back to Enum
    risk_level_enum = sa.Enum("LOW", "HIGH", "UNKNOWN", name="risklevel")
    op.alter_column(
        "evaluation_run",
        "risk_level",
        existing_type=sa.String(),
        type_=risk_level_enum,
        existing_nullable=False,
        postgresql_using="risk_level::risklevel",
    )
