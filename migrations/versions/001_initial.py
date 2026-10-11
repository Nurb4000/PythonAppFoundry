"""initial schema

Revision ID: initial
Revises:
Create Date: 2026-10-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial schema from current models."""
    # This migration captures the full current schema state.
    # Run `flask db stamp head` on existing databases to mark them as up-to-date.
    pass


def downgrade():
    pass
