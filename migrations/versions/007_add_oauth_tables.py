"""add oauth_providers and oauth_tokens tables

Revision ID: add_oauth_tables
Revises: add_api_logs
Create Date: 2026-10-10 00:06:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_oauth_tables'
down_revision = 'add_api_logs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'oauth_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('client_id', sa.String(length=200), nullable=True),
        sa.Column('client_secret', sa.String(length=500), nullable=True),
        sa.Column('authorize_url', sa.String(length=500), nullable=True),
        sa.Column('token_url', sa.String(length=500), nullable=True),
        sa.Column('userinfo_url', sa.String(length=500), nullable=True),
        sa.Column('scopes', sa.String(length=500), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id'),
    )

    op.create_table(
        'oauth_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.String(length=50), nullable=False),
        sa.Column('external_user_id', sa.String(length=200), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=50), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'external_user_id',
                            name='uq_provider_external_user'),
    )


def downgrade():
    op.drop_table('oauth_tokens')
    op.drop_table('oauth_providers')
