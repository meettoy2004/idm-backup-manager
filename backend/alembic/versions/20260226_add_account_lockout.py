"""Add account lockout and session tracking fields to users

Revision ID: 20260226_add_account_lockout
Revises: 20260224_add_system_settings
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa

revision = '20260226_add_account_lockout'
down_revision = '20260224_add_system_settings'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c['name'] for c in sa.inspect(bind).get_columns('users')}

    if 'failed_logins' not in cols:
        op.add_column('users', sa.Column(
            'failed_logins', sa.Integer(), nullable=False, server_default='0'))

    if 'locked_until' not in cols:
        op.add_column('users', sa.Column(
            'locked_until', sa.DateTime(timezone=True), nullable=True))

    if 'last_failed_at' not in cols:
        op.add_column('users', sa.Column(
            'last_failed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'last_failed_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_logins')
