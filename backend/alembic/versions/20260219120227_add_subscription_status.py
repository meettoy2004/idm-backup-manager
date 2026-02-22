"""add subscription status

Revision ID: add_subscription_status
Revises: add_pwd_change_flag
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'add_subscription_status'
down_revision = 'add_pwd_change_flag'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('servers')]
    
    if 'subscription_status' not in columns:
        op.add_column('servers', sa.Column('subscription_status', sa.String(), nullable=True))
    if 'subscription_message' not in columns:
        op.add_column('servers', sa.Column('subscription_message', sa.String(), nullable=True))
    if 'subscription_last_checked' not in columns:
        op.add_column('servers', sa.Column('subscription_last_checked', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('servers', 'subscription_last_checked')
    op.drop_column('servers', 'subscription_message')
    op.drop_column('servers', 'subscription_status')
