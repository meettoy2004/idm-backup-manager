"""Add high-value features: backup size, organizations, notifications, verification, restore, DR templates

Revision ID: 20260222_add_high_value_features
Revises: 20260219120227_add_subscription_status
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = '20260222_add_high_value_features'
down_revision = 'add_subscription_status'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    bind = op.get_bind()
    insp = inspect(bind)
    return column_name in [c['name'] for c in insp.get_columns(table_name)]


def table_exists(table_name):
    bind = op.get_bind()
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def upgrade():
    # 1. Backup Size Tracking
    if not column_exists('backup_jobs', 'backup_size_bytes'):
        op.add_column('backup_jobs', sa.Column('backup_size_bytes', sa.BigInteger(), nullable=True))
    if not column_exists('backup_jobs', 'compressed_size_bytes'):
        op.add_column('backup_jobs', sa.Column('compressed_size_bytes', sa.BigInteger(), nullable=True))

    # 2. Organizations
    if not table_exists('organizations'):
        op.create_table(
            'organizations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(), nullable=False, unique=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        )

    if not table_exists('user_organizations'):
        op.create_table(
            'user_organizations',
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('role', sa.String(), server_default='member', nullable=False),
            sa.PrimaryKeyConstraint('user_id', 'organization_id'),
        )

    if not column_exists('servers', 'organization_id'):
        op.add_column('servers', sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True))

    if not column_exists('backup_configs', 'organization_id'):
        op.add_column('backup_configs', sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True))

    # 3. Notification Settings
    if not table_exists('notification_settings'):
        op.create_table(
            'notification_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
            sa.Column('notify_on_failure', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('notify_on_success', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('notify_threshold', sa.Integer(), server_default='3', nullable=False),
            sa.Column('email_addresses', postgresql.ARRAY(sa.Text()), nullable=True),
            sa.Column('slack_webhook_url', sa.String(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 4. Verification Logs
    if not table_exists('verification_logs'):
        op.create_table(
            'verification_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('job_id', sa.Integer(), sa.ForeignKey('backup_jobs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('verification_status', sa.String(), nullable=False),
            sa.Column('gpg_verify_output', sa.Text(), nullable=True),
            sa.Column('integrity_check_passed', sa.Boolean(), nullable=True),
            sa.Column('verified_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
        )

    # 5. Restore Operations
    if not table_exists('restore_operations'):
        op.create_table(
            'restore_operations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('job_id', sa.Integer(), sa.ForeignKey('backup_jobs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('server_id', sa.Integer(), sa.ForeignKey('servers.id', ondelete='SET NULL'), nullable=True),
            sa.Column('requested_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('restore_status', sa.String(), server_default='pending', nullable=False),
            sa.Column('restore_path', sa.String(), nullable=True),
            sa.Column('gpg_decrypt_output', sa.Text(), nullable=True),
            sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 6. DR Templates
    if not table_exists('dr_templates'):
        op.create_table(
            'dr_templates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('template_config', postgresql.JSONB(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade():
    for t in ['dr_templates', 'restore_operations', 'verification_logs', 'notification_settings']:
        if table_exists(t):
            op.drop_table(t)
    bind = op.get_bind()
    insp = inspect(bind)
    for tbl, col in [('backup_configs', 'organization_id'), ('servers', 'organization_id')]:
        if col in [c['name'] for c in insp.get_columns(tbl)]:
            op.drop_column(tbl, col)
    for t in ['user_organizations', 'organizations']:
        if table_exists(t):
            op.drop_table(t)
    for col in ['compressed_size_bytes', 'backup_size_bytes']:
        if col in [c['name'] for c in insp.get_columns('backup_jobs')]:
            op.drop_column('backup_jobs', col)
