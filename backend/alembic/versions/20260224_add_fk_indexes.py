"""Add missing indexes on foreign key columns

Revision ID: 20260224_add_fk_indexes
Revises: 20260222_add_high_value_features
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20260224_add_fk_indexes'
down_revision = '20260222_add_high_value_features'
branch_labels = None
depends_on = None


def index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    # Check across all tables
    for table_name in insp.get_table_names():
        for idx in insp.get_indexes(table_name):
            if idx['name'] == index_name:
                return True
    return False


def upgrade() -> None:
    # backup_jobs.server_id — queried constantly in the polling loop
    if not index_exists('ix_backup_jobs_server_id'):
        op.create_index('ix_backup_jobs_server_id', 'backup_jobs', ['server_id'])

    # backup_jobs.started_at — used in deduplication query (server_id + started_at)
    if not index_exists('ix_backup_jobs_started_at'):
        op.create_index('ix_backup_jobs_started_at', 'backup_jobs', ['started_at'])

    # backup_configs.server_id — used when loading configs per server
    if not index_exists('ix_backup_configs_server_id'):
        op.create_index('ix_backup_configs_server_id', 'backup_configs', ['server_id'])

    # restore_operations.server_id — filtered in list_restores
    if not index_exists('ix_restore_operations_server_id'):
        try:
            op.create_index('ix_restore_operations_server_id', 'restore_operations', ['server_id'])
        except Exception:
            pass  # table may not exist in all environments

    # verification_logs.job_id — filtered in list_verifications
    if not index_exists('ix_verification_logs_job_id'):
        try:
            op.create_index('ix_verification_logs_job_id', 'verification_logs', ['job_id'])
        except Exception:
            pass


def downgrade() -> None:
    for idx, table in [
        ('ix_backup_jobs_server_id',        'backup_jobs'),
        ('ix_backup_jobs_started_at',        'backup_jobs'),
        ('ix_backup_configs_server_id',      'backup_configs'),
        ('ix_restore_operations_server_id',  'restore_operations'),
        ('ix_verification_logs_job_id',      'verification_logs'),
    ]:
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass
