"""add is_system and requirements_text to modules

Revision ID: add_module_fields
Revises: add_allowed_groups
Create Date: 2026-10-10 00:02:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_module_fields'
down_revision = 'add_allowed_groups'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('modules', sa.Column('is_system', sa.Boolean(), server_default='0'))
    op.add_column('modules', sa.Column('requirements_text', sa.Text(), server_default=''))


def downgrade():
    op.drop_column('modules', 'requirements_text')
    op.drop_column('modules', 'is_system')
