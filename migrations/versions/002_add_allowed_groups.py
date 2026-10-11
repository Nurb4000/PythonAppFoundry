"""add allowed_groups to routes

Revision ID: add_allowed_groups
Revises: initial
Create Date: 2026-10-10 00:01:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_allowed_groups'
down_revision = 'initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('routes', sa.Column('allowed_groups', sa.Text(), server_default=''))


def downgrade():
    op.drop_column('routes', 'allowed_groups')
