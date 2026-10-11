"""add module_id to query_reports

Revision ID: add_query_reports_module_id
Revises: add_module_fields
Create Date: 2026-10-10 00:03:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_query_reports_module_id'
down_revision = 'add_module_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('query_reports', sa.Column('module_id', sa.Integer(),
                sa.ForeignKey('modules.id')))


def downgrade():
    op.drop_column('query_reports', 'module_id')
