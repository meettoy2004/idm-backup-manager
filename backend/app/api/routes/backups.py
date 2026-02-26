from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.backup_config import BackupConfig
from ...models.server import Server
from ...services.deployment_service import DeploymentService
from ...services.audit_service import log_action, AuditAction
from pydantic import BaseModel, Field

router = APIRouter()

class BackupConfigCreate(BaseModel):
    server_id: int = Field(..., gt=0)
    schedule: str = Field(..., min_length=1, max_length=100)
    retention_count: int = Field(10, ge=1, le=9999)
    s3_mount_dir: str = Field("/mnt/idm-backup", min_length=1, max_length=500)
    backup_dir: str = Field("/var/lib/ipa/backup", min_length=1, max_length=500)

class BackupConfigUpdate(BaseModel):
    schedule: Optional[str] = None
    retention_count: Optional[int] = None
    s3_mount_dir: Optional[str] = None
    backup_dir: Optional[str] = None
    is_enabled: Optional[bool] = None

class BackupConfigResponse(BaseModel):
    id: int
    server_id: int
    schedule: str
    retention_count: int
    s3_mount_dir: str
    backup_dir: str
    is_enabled: bool
    class Config:
        from_attributes = True

@router.get("", response_model=List[BackupConfigResponse])
@router.get("/", response_model=List[BackupConfigResponse])
def list_backup_configs(db: Session = Depends(get_db)):
    return db.query(BackupConfig).all()

@router.post("", response_model=BackupConfigResponse)
@router.post("/", response_model=BackupConfigResponse)
def create_backup_config(config: BackupConfigCreate, request: Request, db: Session = Depends(get_db)):
    db_config = BackupConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    server = db.query(Server).filter(Server.id == config.server_id).first()
    log_action(db, AuditAction.CONFIG_CREATED, resource="backups",
        resource_id=db_config.id,
        detail=f"Created backup config for '{server.name if server else config.server_id}'",
        ip_address=request.client.host)
    return db_config

@router.get("/{config_id}", response_model=BackupConfigResponse)
@router.get("/{config_id}/", response_model=BackupConfigResponse)
def get_backup_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(BackupConfig).filter(BackupConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Backup config not found")
    return config

class BackupConfigUpdateResponse(BaseModel):
    id: int
    server_id: int
    schedule: str
    retention_count: int
    s3_mount_dir: str
    backup_dir: str
    is_enabled: bool
    deploy_status: Optional[str] = None   # "deployed", "skipped", or error message
    class Config:
        from_attributes = True

@router.put("/{config_id}", response_model=BackupConfigUpdateResponse)
@router.put("/{config_id}/", response_model=BackupConfigUpdateResponse)
def update_backup_config(config_id: int, updates: BackupConfigUpdate, request: Request, db: Session = Depends(get_db)):
    config = db.query(BackupConfig).filter(BackupConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Backup config not found")

    if updates.schedule is not None:
        config.schedule = updates.schedule
    if updates.retention_count is not None:
        config.retention_count = updates.retention_count
    if updates.s3_mount_dir is not None:
        config.s3_mount_dir = updates.s3_mount_dir
    if updates.backup_dir is not None:
        config.backup_dir = updates.backup_dir
    if updates.is_enabled is not None:
        config.is_enabled = updates.is_enabled

    db.commit()
    db.refresh(config)

    log_action(db, AuditAction.CONFIG_UPDATED, resource="backups",
        resource_id=config_id,
        detail=f"Updated backup config {config_id}",
        ip_address=request.client.host)

    # Auto-deploy updated config to the server so changes take effect immediately
    deploy_status = "skipped"
    server = config.server
    if server and server.is_active and config.is_enabled:
        try:
            deploy_cfg = {
                'schedule': config.schedule,
                'retention_count': config.retention_count,
                's3_mount_dir': config.s3_mount_dir,
                'backup_dir': config.backup_dir,
            }
            success, message = DeploymentService().deploy_backup_configuration(
                hostname=server.hostname,
                port=server.port,
                username=server.username,
                config=deploy_cfg,
                server_name=server.name,
            )
            deploy_status = "deployed" if success else f"deploy failed: {message}"
            log_action(db, AuditAction.CONFIG_DEPLOYED, resource="backups",
                resource_id=config_id,
                detail=f"Auto-deployed updated config to '{server.name}' — {'success' if success else 'failed'}: {message}",
                ip_address=request.client.host,
                status="success" if success else "failure")
        except Exception as e:
            deploy_status = f"deploy error: {str(e)}"

    result = BackupConfigUpdateResponse(
        id=config.id, server_id=config.server_id, schedule=config.schedule,
        retention_count=config.retention_count, s3_mount_dir=config.s3_mount_dir,
        backup_dir=config.backup_dir, is_enabled=config.is_enabled,
        deploy_status=deploy_status,
    )
    return result

@router.delete("/{config_id}")
@router.delete("/{config_id}/")
def delete_backup_config(config_id: int, request: Request, db: Session = Depends(get_db)):
    config = db.query(BackupConfig).filter(BackupConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Backup config not found")
    
    db.delete(config)
    db.commit()
    
    log_action(db, AuditAction.CONFIG_DELETED, resource="backups",
        resource_id=config_id,
        detail=f"Deleted backup config {config_id}",
        ip_address=request.client.host)
    return {"message": "Backup config deleted"}

@router.post("/{config_id}/deploy")
@router.post("/{config_id}/deploy/")
def deploy_backup_config(config_id: int, request: Request, db: Session = Depends(get_db)):
    config = db.query(BackupConfig).filter(BackupConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Backup config not found")
    
    server = config.server
    if not server.is_active:
        raise HTTPException(status_code=400, detail="Server is not active")
    
    deploy_config = {
        'schedule': config.schedule,
        'retention_count': config.retention_count,
        's3_mount_dir': config.s3_mount_dir,
        'backup_dir': config.backup_dir
    }
    
    success, message = DeploymentService().deploy_backup_configuration(
        hostname=server.hostname,
        port=server.port,
        username=server.username,
        config=deploy_config,
        server_name=server.name
    )
    
    log_action(db, AuditAction.CONFIG_DEPLOYED, resource="backups",
        resource_id=config_id,
        detail=f"Deployed config to '{server.name}' ({server.hostname}) — {'success' if success else 'failed'}: {message}",
        ip_address=request.client.host,
        status="success" if success else "failure")
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"message": message, "server": server.name, "vault_key_path": f"secret/backup-keys/{server.name}"}
