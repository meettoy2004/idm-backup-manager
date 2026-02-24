"""add system_settings table

Revision ID: 20260224_add_system_settings
Revises: 20260224_add_fk_indexes
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = '20260224_add_system_settings'
down_revision = '20260224_add_fk_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_settings',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('key',        sa.String(255),   nullable=False),
        sa.Column('value',      sa.Text(),        nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_system_settings_key', 'system_settings', ['key'], unique=True)


def downgrade():
    op.drop_index('ix_system_settings_key', table_name='system_settings')
    op.drop_table('system_settings')
