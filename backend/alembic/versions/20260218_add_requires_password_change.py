"""add requires password change

Revision ID: add_pwd_change_flag
Revises: b75868ff2ec1
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'add_pwd_change_flag'
down_revision = 'b75868ff2ec1'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'requires_password_change' not in columns:
        op.add_column('users', sa.Column('requires_password_change', sa.Boolean(), server_default='false', nullable=False))

def downgrade():
    op.drop_column('users', 'requires_password_change')
