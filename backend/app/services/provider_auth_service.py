import httpx
import logging
from typing import Optional
from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
from ldap3.core.exceptions import LDAPException
from sqlalchemy.orm import Session
from ..models.auth_provider import AuthProvider
from ..models.user import User
from .auth_service import get_or_create_oidc_user, create_access_token
from datetime import datetime

logger = logging.getLogger(__name__)

# ── OIDC / Keycloak ────────────────────────────────────────────────────────

def get_keycloak_urls(config: dict) -> dict:
    base = config["base_url"].rstrip("/")
    realm = config["realm"]
    return {
        "auth":     f"{base}/realms/{realm}/protocol/openid-connect/auth",
        "token":    f"{base}/realms/{realm}/protocol/openid-connect/token",
        "userinfo": f"{base}/realms/{realm}/protocol/openid-connect/userinfo",
        "logout":   f"{base}/realms/{realm}/protocol/openid-connect/logout",
        "certs":    f"{base}/realms/{realm}/protocol/openid-connect/certs",
    }

async def exchange_keycloak_code(code: str, redirect_uri: str, config: dict) -> dict:
    urls = get_keycloak_urls(config)
    async with httpx.AsyncClient(verify=config.get("verify_ssl", True)) as client:
        resp = await client.post(urls["token"], data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": redirect_uri,
            "client_id":    config["client_id"],
            "client_secret": config.get("client_secret", ""),
        })
        if resp.status_code != 200:
            raise ValueError(f"Token exchange failed: {resp.text}")
        tokens = resp.json()

        # Get userinfo
        userinfo = await client.get(urls["userinfo"],
            headers={"Authorization": f"Bearer {tokens['access_token']}"})
        return userinfo.json()

# ── LDAP ───────────────────────────────────────────────────────────────────

def authenticate_ldap(username: str, password: str, config: dict) -> Optional[dict]:
    """
    Authenticate against LDAP/AD.
    Returns user attributes dict on success, None on failure.
    config keys: host, port, use_ssl, bind_dn, bind_password,
                 search_base, search_filter, attr_email, attr_name
    """
    try:
        server = Server(
            config["host"],
            port=int(config.get("port", 389)),
            use_ssl=config.get("use_ssl", False),
            get_info=ALL
        )

        # First bind with service account to search
        bind_dn = config.get("bind_dn", "")
        bind_pw = config.get("bind_password", "")

        conn = Connection(server, user=bind_dn, password=bind_pw,
                          authentication=SIMPLE, auto_bind=True)

        # Search for user
        search_filter = config.get("search_filter", "(uid={username})")
        search_filter = search_filter.replace("{username}", username)
        search_base   = config["search_base"]

        attr_email = config.get("attr_email", "mail")
        attr_name  = config.get("attr_name", "cn")

        conn.search(search_base, search_filter,
                    attributes=[attr_email, attr_name, "dn"])

        if not conn.entries:
            logger.warning(f"LDAP: user '{username}' not found")
            return None

        user_dn    = conn.entries[0].entry_dn
        user_email = str(conn.entries[0][attr_email]) if attr_email in conn.entries[0] else ""
        user_name  = str(conn.entries[0][attr_name])  if attr_name  in conn.entries[0] else username
        conn.unbind()

        # Now bind as the user to verify password
        user_conn = Connection(server, user=user_dn, password=password,
                               authentication=SIMPLE, auto_bind=True)
        user_conn.unbind()

        return {
            "sub":      user_dn,
            "email":    user_email or f"{username}@ldap",
            "name":     user_name,
            "username": username,
        }

    except LDAPException as e:
        logger.warning(f"LDAP auth failed for '{username}': {e}")
        return None
    except Exception as e:
        logger.error(f"LDAP error: {e}")
        return None

def test_ldap_connection(config: dict) -> dict:
    """Test LDAP connectivity and service account bind"""
    try:
        server = Server(
            config["host"],
            port=int(config.get("port", 389)),
            use_ssl=config.get("use_ssl", False),
            get_info=ALL
        )
        conn = Connection(server,
            user=config.get("bind_dn", ""),
            password=config.get("bind_password", ""),
            authentication=SIMPLE, auto_bind=True)
        info = str(server.info.vendor_name) if server.info else "Unknown"
        conn.unbind()
        return {"success": True, "message": f"Connected to LDAP server. Vendor: {info}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ── SAML ───────────────────────────────────────────────────────────────────

def get_saml_settings(config: dict, base_url: str) -> dict:
    """Build python3-saml settings dict from stored config"""
    sp_entity_id  = config.get("sp_entity_id",  f"{base_url}/api/v1/auth/saml/metadata")
    acs_url       = config.get("acs_url",        f"{base_url}/api/v1/auth/saml/callback")
    return {
        "strict": True,
        "debug":  False,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url":     acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            },
            "singleLogoutService": {
                "url":     f"{base_url}/api/v1/auth/saml/logout",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": config.get("sp_cert", ""),
            "privateKey": config.get("sp_key",  ""),
        },
        "idp": {
            "entityId": config.get("idp_entity_id", ""),
            "singleSignOnService": {
                "url":     config.get("idp_sso_url", ""),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "singleLogoutService": {
                "url":     config.get("idp_slo_url", ""),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": config.get("idp_cert", ""),
        }
    }
