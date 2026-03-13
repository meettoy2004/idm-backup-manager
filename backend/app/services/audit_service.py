from sqlalchemy.orm import Session
from ..models.audit_log import AuditLog
from datetime import datetime

class AuditAction:
    LOGIN_SUCCESS    = "LOGIN_SUCCESS"
    LOGIN_FAILED     = "LOGIN_FAILED"
    ACCOUNT_LOCKED   = "ACCOUNT_LOCKED"
    LOGOUT           = "LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    USER_CREATED     = "USER_CREATED"
    USER_UPDATED     = "USER_UPDATED"
    USER_DELETED     = "USER_DELETED"
    SERVER_CREATED   = "SERVER_CREATED"
    SERVER_DELETED   = "SERVER_DELETED"
    SERVER_UPDATED   = "SERVER_UPDATED"
    CONFIG_CREATED   = "CONFIG_CREATED"
    CONFIG_UPDATED   = "CONFIG_UPDATED"
    CONFIG_DELETED   = "CONFIG_DELETED"
    CONFIG_DEPLOYED  = "CONFIG_DEPLOYED"
    JOB_TRIGGERED    = "JOB_TRIGGERED"
    JOB_COMPLETED    = "JOB_COMPLETED"
    JOB_FAILED       = "JOB_FAILED"
    RESTORE_TRIGGERED = "RESTORE_TRIGGERED"
    RESTORE_COMPLETED = "RESTORE_COMPLETED"
    RESTORE_FAILED    = "RESTORE_FAILED"
    RESTORE_CANCELLED = "RESTORE_CANCELLED"

def log_action(
    db: Session,
    action: str,
    user: str = "system",
    auth_method: str = None,
    resource: str = None,
    resource_id: str = None,
    detail: str = None,
    extra_data: dict = None,
    ip_address: str = None,
    status: str = "success"
):
    entry = AuditLog(
        action=action,
        user=user,
        auth_method=auth_method,
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
        detail=detail,
        extra_data=extra_data,
        ip_address=ip_address,
        status=status
    )
    db.add(entry)
    db.commit()
    return entry
