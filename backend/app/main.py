from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .config import settings
from .api.routes import servers, backups, jobs, stats, audit, auth, auth_providers
from .api.routes import organizations, notifications, verifications, restores, dr_templates, reports
from .api.routes import system_settings

# Rate limiter — keyed on client IP
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title="IdM Backup Manager", version="2.0.0", redirect_slashes=False)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(servers.router,        prefix="/api/v1/servers",        tags=["servers"])
app.include_router(backups.router,        prefix="/api/v1/backups",        tags=["backups"])
app.include_router(jobs.router,           prefix="/api/v1/jobs",           tags=["jobs"])
app.include_router(stats.router,          prefix="/api/v1/stats",          tags=["stats"])
app.include_router(audit.router,          prefix="/api/v1/audit",          tags=["audit"])
app.include_router(auth.router,           prefix="/api/v1/auth",           tags=["auth"])
app.include_router(auth_providers.router, prefix="/api/v1/providers",      tags=["providers"])
app.include_router(organizations.router,  prefix="/api/v1/organizations",  tags=["organizations"])
app.include_router(notifications.router,  prefix="/api/v1/notifications",  tags=["notifications"])
app.include_router(verifications.router,  prefix="/api/v1/verifications",  tags=["verifications"])
app.include_router(restores.router,       prefix="/api/v1/restores",       tags=["restores"])
app.include_router(dr_templates.router,   prefix="/api/v1/dr-templates",   tags=["dr-templates"])
app.include_router(reports.router,         prefix="/api/v1/reports",        tags=["reports"])
app.include_router(system_settings.router, prefix="/api/v1/settings",       tags=["settings"])

@app.get("/health")
@app.get("/health/")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}
