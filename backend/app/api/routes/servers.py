import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.server import Server
from ...models.backup_config import BackupConfig
from ...models.backup_job import BackupJob
from ...models.user import User
from ...services.audit_service import log_action, AuditAction
from ...api.deps import get_current_user, require_admin, require_editor
from pydantic import BaseModel, Field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

class ServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    hostname: str = Field(..., min_length=1, max_length=255)
    port: int = Field(22, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=100)
    description: str = Field(None, max_length=1000)

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
def list_servers(db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    return db.query(Server).all()

@router.post("", response_model=ServerResponse)
@router.post("/", response_model=ServerResponse)
def create_server(server: ServerCreate, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(require_editor)):
    db_server = Server(**server.dict())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    log_action(db, AuditAction.SERVER_CREATED, user=current_user.email,
        resource="servers", resource_id=db_server.id,
        detail=f"Created server '{db_server.name}' ({db_server.hostname})",
        ip_address=request.client.host)
    return db_server

@router.get("/{server_id}", response_model=ServerResponse)
@router.get("/{server_id}/", response_model=ServerResponse)
def get_server(server_id: int, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@router.put("/{server_id}")
@router.put("/{server_id}/")
def update_server(server_id: int, updates: ServerCreate, request: Request,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(require_editor)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    update_data = updates.dict(exclude_unset=True)
    if 'name' in update_data:
        server.name = update_data['name']
    if 'hostname' in update_data:
        server.hostname = update_data['hostname']
    if 'port' in update_data:
        server.port = update_data['port']
    if 'username' in update_data:
        server.username = update_data['username']
    if 'description' in update_data:
        server.description = update_data['description']

    db.commit()
    db.refresh(server)
    log_action(db, AuditAction.SERVER_UPDATED, user=current_user.email,
        resource="servers", resource_id=server_id,
        detail=f"Updated server '{server.name}'",
        ip_address=request.client.host)
    return server

@router.delete("/{server_id}")
@router.delete("/{server_id}/")
def delete_server(server_id: int, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    name = server.name
    # Delete related records first
    db.query(BackupJob).filter(BackupJob.server_id == server_id).delete()
    db.query(BackupConfig).filter(BackupConfig.server_id == server_id).delete()
    db.delete(server)
    db.commit()
    
    log_action(db, AuditAction.SERVER_DELETED, user=current_user.email,
        resource="servers", resource_id=server_id,
        detail=f"Deleted server '{name}'",
        ip_address=request.client.host)
    return {"message": f"Server {name} deleted"}

@router.get("/{server_id}/system-status")
@router.get("/{server_id}/system-status/")
def get_server_system_status(server_id: int, db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    """SSH into server and return disk usage + IPA service status."""
    from ...services.ssh_service import SSHService

    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    try:
        ssh = SSHService()
        client = ssh.connect(server.hostname, server.port, server.username)

        _, root_out,   _ = ssh.execute_command(client, "df -hT /")
        _, backup_out, _ = ssh.execute_command(client, "df -h /var/lib/ipa/backup 2>/dev/null || true")
        _, ipa_out,    _ = ssh.execute_command(client, "sudo ipactl status 2>&1 || true")

        client.close()

        return {
            "server_id":   server_id,
            "server_name": server.name,
            "hostname":    server.hostname,
            "root_disk":   _parse_df(root_out),
            "backup_disk": _parse_df(backup_out),
            "ipa_services": _parse_ipactl(ipa_out),
            "error": None,
        }
    except Exception as e:
        logger.warning("system-status failed for server %s: %s", server_id, e)
        return {
            "server_id":   server_id,
            "server_name": server.name,
            "hostname":    server.hostname,
            "root_disk":   None,
            "backup_disk": None,
            "ipa_services": [],
            "error": str(e),
        }


def _parse_df(output: str):
    """Parse the first data line of df output into a dict."""
    lines = [l for l in output.strip().splitlines() if l and not l.startswith("Filesystem")]
    if not lines:
        return None
    parts = lines[0].split()
    # df -hT has 7 cols (Filesystem Type Size Used Avail Use% Mount)
    # df -h  has 6 cols (Filesystem     Size Used Avail Use% Mount)
    if len(parts) == 7:
        return {"filesystem": parts[0], "type": parts[1], "size": parts[2],
                "used": parts[3], "avail": parts[4], "use_pct": parts[5], "mount": parts[6]}
    if len(parts) >= 6:
        return {"filesystem": parts[0], "type": None, "size": parts[1],
                "used": parts[2], "avail": parts[3], "use_pct": parts[4], "mount": parts[5]}
    return None


def _parse_ipactl(output: str):
    """Parse ipactl status output into [{service, status}]."""
    services = []
    for line in output.strip().splitlines():
        line = line.strip()
        if ": " in line and not line.lower().startswith("redirect"):
            svc, _, st = line.partition(": ")
            services.append({"service": svc.strip(), "status": st.strip()})
    return services


@router.get("/{server_id}/check-subscription")
@router.get("/{server_id}/check-subscription/")
def check_subscription_manager(server_id: int, db: Session = Depends(get_db),
                                current_user: User = Depends(get_current_user)):
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
        logger.exception("Error checking subscription for server %s", server_id)
        result = {"configured": False, "enabled": False, "status": "error", 
                "message": str(e)}
        # Save error to database
        server.subscription_status = result['status']
        server.subscription_message = result['message']
        server.subscription_last_checked = datetime.now(timezone.utc)
        db.commit()
        return result
