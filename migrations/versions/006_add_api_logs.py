"""add api_logs table for API request/response logging

Revision ID: add_api_logs
Revises: add_api_key_rate_limits
Create Date: 2026-10-10 00:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_api_logs'
down_revision = 'add_api_key_rate_limits'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('client_ip', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('request_body', sa.Text(), nullable=True),
        sa.Column('response_summary', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_api_logs_created_at'), 'api_logs', ['created_at'])


def downgrade():
    op.drop_index(op.f('ix_api_logs_created_at'), table_name='api_logs')
    op.drop_table('api_logs')
