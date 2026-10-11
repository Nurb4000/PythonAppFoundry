"""add rate limit fields to api_keys

Revision ID: add_api_key_rate_limits
Revises: add_query_reports_module_id
Create Date: 2026-10-10 00:04:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_api_key_rate_limits'
down_revision = 'add_query_reports_module_id'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('api_keys', sa.Column('max_requests_per_minute', sa.Integer(), server_default='60'))
    op.add_column('api_keys', sa.Column('max_requests_per_hour', sa.Integer(), server_default='1000'))


def downgrade():
    op.drop_column('api_keys', 'max_requests_per_hour')
    op.drop_column('api_keys', 'max_requests_per_minute')
