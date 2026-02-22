from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from ...config.database import get_db
from ...models.auth_provider import AuthProvider
from ...models.user import User
from ...services.auth_service import create_access_token, get_or_create_oidc_user
from ...services.provider_auth_service import (
    get_keycloak_urls, exchange_keycloak_code,
    authenticate_ldap, test_ldap_connection, get_saml_settings
)
from ...services.audit_service import log_action, AuditAction
from ...api.deps import require_admin, get_current_user
from ...config import settings
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# ── Schemas ────────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    name:       str
    type:       str   # oidc / ldap / saml
    is_enabled: bool  = True
    config:     dict  = {}

class ProviderResponse(BaseModel):
    id:         int
    name:       str
    type:       str
    is_enabled: bool
    config:     dict
    created_at: datetime
    class Config:
        from_attributes = True

class ProviderPublic(BaseModel):
    id:   int
    name: str
    type: str

class LDAPLoginRequest(BaseModel):
    provider_id: int
    username:    str
    password:    str

# ── CRUD ───────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ProviderResponse])
@router.get("/", response_model=List[ProviderResponse])
def list_providers(db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    return db.query(AuthProvider).all()

@router.get("/public", response_model=List[ProviderPublic])
@router.get("/public/", response_model=List[ProviderPublic])
def list_public_providers(db: Session = Depends(get_db)):
    """Returns enabled providers for the login page (no secrets)"""
    providers = db.query(AuthProvider).filter(AuthProvider.is_enabled == True).all()
    return [{"id": p.id, "name": p.name, "type": p.type} for p in providers]

@router.post("", response_model=ProviderResponse)
@router.post("/", response_model=ProviderResponse)
def create_provider(body: ProviderCreate, request: Request,
                    db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    provider = AuthProvider(name=body.name, type=body.type,
                            is_enabled=body.is_enabled, config=body.config)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    log_action(db, "PROVIDER_CREATED", user=admin.email,
        detail=f"Created {body.type} provider '{body.name}'",
        ip_address=request.client.host)
    return provider

@router.put("/{provider_id}", response_model=ProviderResponse)
@router.put("/{provider_id}/", response_model=ProviderResponse)
def update_provider(provider_id: int, body: ProviderCreate, request: Request,
                    db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    provider = db.query(AuthProvider).filter(AuthProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.name       = body.name
    provider.type       = body.type
    provider.is_enabled = body.is_enabled
    provider.config     = body.config
    db.commit()
    db.refresh(provider)
    log_action(db, "PROVIDER_UPDATED", user=admin.email,
        detail=f"Updated {body.type} provider '{body.name}'",
        ip_address=request.client.host)
    return provider

@router.delete("/{provider_id}")
@router.delete("/{provider_id}/")
def delete_provider(provider_id: int, request: Request,
                    db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    provider = db.query(AuthProvider).filter(AuthProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    log_action(db, "PROVIDER_DELETED", user=admin.email,
        detail=f"Deleted provider '{provider.name}'",
        ip_address=request.client.host)
    return {"message": "Provider deleted"}

# ── Test connection ────────────────────────────────────────────────────────

@router.post("/{provider_id}/test")
@router.post("/{provider_id}/test/")
async def test_provider(provider_id: int, db: Session = Depends(get_db),
                        admin: User = Depends(require_admin)):
    provider = db.query(AuthProvider).filter(AuthProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if provider.type == "ldap":
        return test_ldap_connection(provider.config)

    elif provider.type == "oidc":
        try:
            urls = get_keycloak_urls(provider.config)
            async with __import__("httpx").AsyncClient(
                verify=provider.config.get("verify_ssl", True)
            ) as client:
                resp = await client.get(urls["certs"])
            if resp.status_code == 200:
                return {"success": True, "message": "Keycloak reachable — JWKS endpoint OK"}
            return {"success": False, "message": f"Keycloak returned {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    return {"success": False, "message": f"Test not supported for type '{provider.type}'"}

# ── OIDC / Keycloak flow ───────────────────────────────────────────────────

@router.get("/{provider_id}/oidc/redirect")
async def oidc_redirect(provider_id: int, request: Request,
                        db: Session = Depends(get_db)):
    provider = db.query(AuthProvider).filter(
        AuthProvider.id == provider_id, AuthProvider.type == "oidc",
        AuthProvider.is_enabled == True
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="OIDC provider not found")

    urls         = get_keycloak_urls(provider.config)
    redirect_uri = f"{request.base_url}api/v1/providers/{provider_id}/oidc/callback"
    scope        = provider.config.get("scope", "openid email profile")

    url = (f"{urls['auth']}?client_id={provider.config['client_id']}"
           f"&redirect_uri={redirect_uri}"
           f"&response_type=code&scope={scope}&state={provider_id}")
    return RedirectResponse(url)

@router.get("/{provider_id}/oidc/callback")
async def oidc_callback(provider_id: int, code: str, request: Request,
                        db: Session = Depends(get_db)):
    provider = db.query(AuthProvider).filter(
        AuthProvider.id == provider_id, AuthProvider.type == "oidc"
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="OIDC provider not found")

    redirect_uri = f"{request.base_url}api/v1/providers/{provider_id}/oidc/callback"

    try:
        claims = await exchange_keycloak_code(code, redirect_uri, provider.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user  = get_or_create_oidc_user(db, claims)
    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})

    log_action(db, AuditAction.LOGIN_SUCCESS, user=user.email, auth_method="oidc",
        detail=f"Keycloak OIDC login via '{provider.name}' for '{user.email}'",
        ip_address=request.client.host)

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(f"{frontend_url}/#/auth/callback?token={token}")

# ── LDAP login ─────────────────────────────────────────────────────────────

@router.post("/ldap/login")
@router.post("/ldap/login/")
async def ldap_login(body: LDAPLoginRequest, request: Request,
                     db: Session = Depends(get_db)):
    provider = db.query(AuthProvider).filter(
        AuthProvider.id == body.provider_id,
        AuthProvider.type == "ldap",
        AuthProvider.is_enabled == True
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="LDAP provider not found")

    user_attrs = authenticate_ldap(body.username, body.password, provider.config)
    if not user_attrs:
        log_action(db, AuditAction.LOGIN_FAILED, user=body.username, auth_method="ldap",
            detail=f"LDAP login failed for '{body.username}' via '{provider.name}'",
            ip_address=request.client.host, status="failure")
        raise HTTPException(status_code=401, detail="Invalid LDAP credentials")

    user  = get_or_create_oidc_user(db, user_attrs)
    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})

    log_action(db, AuditAction.LOGIN_SUCCESS, user=user.email, auth_method="ldap",
        detail=f"LDAP login via '{provider.name}' for '{user.email}'",
        ip_address=request.client.host)

    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "username": user.username,
                 "role": user.role, "auth_method": user.auth_method, "full_name": user.full_name}
    }

# ── SAML flow ──────────────────────────────────────────────────────────────

@router.get("/{provider_id}/saml/redirect")
async def saml_redirect(provider_id: int, request: Request,
                        db: Session = Depends(get_db)):
    provider = db.query(AuthProvider).filter(
        AuthProvider.id == provider_id, AuthProvider.type == "saml",
        AuthProvider.is_enabled == True
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SAML provider not found")

    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        base_url      = str(request.base_url).rstrip("/")
        saml_settings = get_saml_settings(provider.config, base_url)
        req = {"https": "off", "http_host": request.url.hostname,
               "script_name": f"/api/v1/providers/{provider_id}/saml/callback",
               "server_port": str(request.url.port or 80),
               "get_data": {}, "post_data": {}}
        auth     = OneLogin_Saml2_Auth(req, saml_settings)
        sso_url  = auth.login()
        return RedirectResponse(sso_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAML error: {e}")

@router.post("/{provider_id}/saml/callback")
async def saml_callback(provider_id: int, request: Request,
                        db: Session = Depends(get_db)):
    provider = db.query(AuthProvider).filter(
        AuthProvider.id == provider_id, AuthProvider.type == "saml"
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SAML provider not found")

    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        body          = await request.form()
        base_url      = str(request.base_url).rstrip("/")
        saml_settings = get_saml_settings(provider.config, base_url)
        req = {"https": "off", "http_host": request.url.hostname,
               "script_name": f"/api/v1/providers/{provider_id}/saml/callback",
               "server_port": str(request.url.port or 80),
               "get_data": {}, "post_data": dict(body)}
        auth = OneLogin_Saml2_Auth(req, saml_settings)
        auth.process_response()
        errors = auth.get_errors()
        if errors:
            raise HTTPException(status_code=400, detail=f"SAML errors: {errors}")

        attrs = auth.get_attributes()
        email = auth.get_nameid()
        name  = attrs.get("displayName", attrs.get("cn", [email]))[0]
        sub   = email

        claims = {"sub": sub, "email": email, "name": name}
        user   = get_or_create_oidc_user(db, claims)
        token  = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})

        log_action(db, AuditAction.LOGIN_SUCCESS, user=user.email, auth_method="saml",
            detail=f"SAML login via '{provider.name}' for '{user.email}'",
            ip_address=request.client.host)

        frontend_url = settings.FRONTEND_URL
        return RedirectResponse(f"{frontend_url}/#/auth/callback?token={token}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAML processing error: {e}")

@router.get("/{provider_id}/saml/metadata")
async def saml_metadata(provider_id: int, request: Request,
                        db: Session = Depends(get_db)):
    provider = db.query(AuthProvider).filter(
        AuthProvider.id == provider_id, AuthProvider.type == "saml"
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SAML provider not found")
    try:
        from onelogin.saml2.metadata import OneLogin_Saml2_Metadata
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
        base_url      = str(request.base_url).rstrip("/")
        saml_settings = get_saml_settings(provider.config, base_url)
        settings_obj  = OneLogin_Saml2_Settings(saml_settings, sp_validation_only=True)
        metadata      = settings_obj.get_sp_metadata()
        return HTMLResponse(content=metadata, media_type="text/xml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
