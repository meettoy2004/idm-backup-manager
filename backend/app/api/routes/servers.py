from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.server import Server
from ...models.backup_config import BackupConfig
from ...models.backup_job import BackupJob
from ...services.audit_service import log_action, AuditAction
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter()

class ServerCreate(BaseModel):
    name: str
    hostname: str
    port: int = 22
    username: str
    description: str = None

class ServerResponse(BaseModel):
    id: int
    name: str
    hostname: str
    port: int
    username: str
    description: Optional[str] = None
    is_active: bool
    subscription_status: Optional[str] = None
    subscription_message: Optional[str] = None
    subscription_last_checked: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

@router.get("", response_model=List[ServerResponse])
@router.get("/", response_model=List[ServerResponse])
def list_servers(db: Session = Depends(get_db)):
    return db.query(Server).all()

@router.post("", response_model=ServerResponse)
@router.post("/", response_model=ServerResponse)
def create_server(server: ServerCreate, request: Request, db: Session = Depends(get_db)):
    db_server = Server(**server.dict())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    log_action(db, AuditAction.SERVER_CREATED, resource="servers",
        resource_id=db_server.id,
        detail=f"Created server '{db_server.name}' ({db_server.hostname})",
        ip_address=request.client.host)
    return db_server

@router.get("/{server_id}", response_model=ServerResponse)
@router.get("/{server_id}/", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.put("/{server_id}")
@router.put("/{server_id}/")
def update_server(server_id: int, updates: dict, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if 'name' in updates:
        server.name = updates['name']
    if 'hostname' in updates:
        server.hostname = updates['hostname']
    if 'port' in updates:
        server.port = updates['port']
    if 'username' in updates:
        server.username = updates['username']
    if 'description' in updates:
        server.description = updates['description']
    if 'is_active' in updates:
        server.is_active = updates['is_active']
    
    db.commit()
    db.refresh(server)
    return server

@router.delete("/{server_id}")
@router.delete("/{server_id}/")
def delete_server(server_id: int, request: Request, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    name = server.name
    # Delete related records first
    db.query(BackupJob).filter(BackupJob.server_id == server_id).delete()
    db.query(BackupConfig).filter(BackupConfig.server_id == server_id).delete()
    db.delete(server)
    db.commit()
    
    log_action(db, AuditAction.SERVER_DELETED, resource="servers",
        resource_id=server_id,
        detail=f"Deleted server '{name}'",
        ip_address=request.client.host)
    return {"message": f"Server {name} deleted"}

@router.get("/{server_id}/check-subscription")
@router.get("/{server_id}/check-subscription/")
def check_subscription_manager(server_id: int, db: Session = Depends(get_db)):
    """Check if subscription-manager is configured and enabled, then save to database"""
    from ...services.ssh_service import SSHService
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    try:
        ssh = SSHService()
        client = ssh.connect(server.hostname, server.port, server.username)
        
        # Check if subscription-manager is installed
        exit_code, output, error = ssh.execute_command(client, "which subscription-manager")
        if exit_code != 0:
            client.close()
            result = {"configured": False, "enabled": False, "status": "not_installed", 
                    "message": "subscription-manager not installed"}
            # Save to database
            server.subscription_status = result['status']
            server.subscription_message = result['message']
            server.subscription_last_checked = datetime.now(timezone.utc)
            db.commit()
            return result
        
        # Check if system is registered
        exit_code, output, error = ssh.execute_command(client, "sudo subscription-manager status")
        is_registered = "Registered" in output or "Subscribed" in output
        
        # Check if rhsmcertd service is enabled
        exit_code, output, error = ssh.execute_command(client, "systemctl is-enabled rhsmcertd 2>/dev/null || echo disabled")
        is_enabled = "enabled" in output.strip()
        
        client.close()
        
        status = "active" if (is_registered and is_enabled) else "inactive"
        result = {
            "configured": is_registered,
            "enabled": is_enabled,
            "status": status,
            "message": "Active and registered" if status == "active" else "Not fully configured"
        }
        
        # Save to database
        server.subscription_status = result['status']
        server.subscription_message = result['message']
        server.subscription_last_checked = datetime.now(timezone.utc)
        db.commit()
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        result = {"configured": False, "enabled": False, "status": "error", 
                "message": str(e)}
        # Save error to database
        server.subscription_status = result['status']
        server.subscription_message = result['message']
        server.subscription_last_checked = datetime.now(timezone.utc)
        db.commit()
        return result
