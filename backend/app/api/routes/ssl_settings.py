from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...config.database import get_db
from ...models.system_setting import SystemSetting
import os
import logging

logger = logging.getLogger(__name__)

_SSL_DIR = "/ssl"   # backend mount point for the shared ssldata volume

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate

router = APIRouter()


# ── Volume helpers ─────────────────────────────────────────────────────────────

def _write_ssl_files(cert_pem: str, key_pem: str) -> None:
    """Write cert + key to the shared ssldata volume and touch .reload.

    The nginx entrypoint polls for .reload every 5 s and calls `nginx -s reload`
    when it appears, switching to HTTPS mode automatically.  If the volume is
    not mounted (local dev without Docker), this is a no-op.
    """
    ssl_dir = os.environ.get("SSL_DIR", _SSL_DIR)
    if not os.path.isdir(ssl_dir):
        logger.info("SSL volume not mounted at %s — skipping auto-apply", ssl_dir)
        return
    try:
        cert_path  = os.path.join(ssl_dir, "server.crt")
        key_path   = os.path.join(ssl_dir, "server.key")
        flag_path  = os.path.join(ssl_dir, ".reload")
        # Write key first so nginx never sees a cert without its matching key
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(key_pem)
        os.chmod(key_path, 0o644)
        with open(cert_path, "w", encoding="utf-8") as f:
            f.write(cert_pem)
        os.chmod(cert_path, 0o644)
        # Touch the reload trigger — nginx entrypoint picks this up
        open(flag_path, "w").close()
        logger.info("SSL files written to %s; nginx reload triggered", ssl_dir)
    except OSError as exc:
        # Cert is safely in DB regardless — log and continue
        logger.error("Failed to write SSL files to volume: %s", exc)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else default


def _set(db: Session, key: str, value: str):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


# ── Schemas ───────────────────────────────────────────────────────────────────

class CsrRequest(BaseModel):
    common_name:          str
    organization:         str = ""
    organizational_unit:  str = ""
    country:              str = ""   # 2-letter ISO code, e.g. "US"
    state:                str = ""
    city:                 str = ""
    email:                str = ""
    key_size:             int = 2048  # 2048 or 4096


class CertImport(BaseModel):
    certificate: str            # PEM text (signed cert)
    ca_bundle:   Optional[str] = None   # optional CA chain PEM


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def ssl_status(db: Session = Depends(get_db)):
    cert_pem = _get(db, "ssl_certificate")
    has_key  = bool(_get(db, "ssl_private_key"))
    has_csr  = bool(_get(db, "ssl_csr"))

    info: dict = {
        "has_key":         has_key,
        "has_csr":         has_csr,
        "has_certificate": bool(cert_pem),
    }

    if cert_pem:
        try:
            cert = load_pem_x509_certificate(cert_pem.encode())
            cn   = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            info["common_name"] = cn[0].value if cn else ""
            info["not_before"]  = cert.not_valid_before_utc.isoformat()
            info["not_after"]   = cert.not_valid_after_utc.isoformat()
            info["issuer"]      = cert.issuer.rfc4514_string()
        except Exception as exc:
            info["parse_error"] = str(exc)

    return info


# ── Generate CSR ──────────────────────────────────────────────────────────────

@router.post("/csr")
def generate_csr(req: CsrRequest, db: Session = Depends(get_db)):
    if req.key_size not in (2048, 4096):
        raise HTTPException(status_code=422, detail="key_size must be 2048 or 4096")

    # Generate RSA private key
    key = rsa.generate_private_key(public_exponent=65537, key_size=req.key_size)

    # Build subject
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, req.common_name)]
    if req.organization:
        attrs.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, req.organization))
    if req.organizational_unit:
        attrs.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, req.organizational_unit))
    if req.country:
        attrs.append(x509.NameAttribute(NameOID.COUNTRY_NAME, req.country[:2].upper()))
    if req.state:
        attrs.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, req.state))
    if req.city:
        attrs.append(x509.NameAttribute(NameOID.LOCALITY_NAME, req.city))
    if req.email:
        attrs.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, req.email))

    # Build and sign the CSR (self-signed with the new key)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name(attrs))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(req.common_name)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()

    # Store key + CSR; clear any previously imported certificate
    _set(db, "ssl_private_key",  key_pem)
    _set(db, "ssl_csr",          csr_pem)
    _set(db, "ssl_certificate",  "")
    db.commit()

    return {"csr": csr_pem, "message": "CSR generated. Submit it to your CA to obtain a signed certificate."}


# ── Download CSR ──────────────────────────────────────────────────────────────

@router.get("/csr", response_class=PlainTextResponse)
def download_csr(db: Session = Depends(get_db)):
    csr = _get(db, "ssl_csr")
    if not csr:
        raise HTTPException(status_code=404, detail="No CSR generated yet. Generate one first.")
    return PlainTextResponse(
        csr,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="server.csr"'},
    )


# ── Import signed certificate ─────────────────────────────────────────────────

@router.post("/certificate")
def import_certificate(req: CertImport, db: Session = Depends(get_db)):
    cert_pem = req.certificate.strip()
    key_pem  = _get(db, "ssl_private_key")

    if not key_pem:
        raise HTTPException(
            status_code=400,
            detail="No private key on file. Generate a CSR first so the key is stored.",
        )

    # Parse and validate certificate PEM
    try:
        cert = load_pem_x509_certificate(cert_pem.encode())
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid certificate PEM: {exc}")

    # Verify the certificate matches the stored private key
    try:
        key = load_pem_private_key(key_pem.encode(), password=None)
        cert_pub = cert.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        key_pub = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if cert_pub != key_pub:
            raise HTTPException(
                status_code=422,
                detail="Certificate does not match the stored private key. "
                       "Make sure you import the certificate signed for the CSR you generated here.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Key validation error: {exc}")

    # Append CA bundle if provided
    full_pem = cert_pem
    if req.ca_bundle:
        full_pem = cert_pem + "\n" + req.ca_bundle.strip()

    _set(db, "ssl_certificate", full_pem)
    db.commit()

    # Auto-apply: write to shared volume so nginx reloads within ~5 s
    _write_ssl_files(cert_pem=full_pem, key_pem=key_pem)

    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    return {
        "message":     "Certificate imported. nginx will switch to HTTPS within 5 seconds.",
        "common_name": cn[0].value if cn else "",
        "not_after":   cert.not_valid_after_utc.isoformat(),
    }


# ── Download certificate ──────────────────────────────────────────────────────

@router.get("/certificate", response_class=PlainTextResponse)
def download_certificate(db: Session = Depends(get_db)):
    cert = _get(db, "ssl_certificate")
    if not cert:
        raise HTTPException(status_code=404, detail="No certificate imported yet.")
    return PlainTextResponse(
        cert,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="server.crt"'},
    )


# ── Download private key ──────────────────────────────────────────────────────

@router.get("/key", response_class=PlainTextResponse)
def download_key(db: Session = Depends(get_db)):
    key = _get(db, "ssl_private_key")
    if not key:
        raise HTTPException(status_code=404, detail="No private key on file.")
    return PlainTextResponse(
        key,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="server.key"'},
    )


# ── Download nginx.conf with SSL ──────────────────────────────────────────────

@router.get("/nginx-config", response_class=PlainTextResponse)
def download_nginx_config(db: Session = Depends(get_db)):
    if not _get(db, "ssl_certificate"):
        raise HTTPException(status_code=400, detail="No certificate imported yet.")

    config = r"""server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    ssl_certificate     /etc/ssl/idm-toolkit/server.crt;
    ssl_certificate_key /etc/ssl/idm-toolkit/server.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1024;

    location /api/ {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /health {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
"""
    return PlainTextResponse(
        config,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="nginx-ssl.conf"'},
    )
