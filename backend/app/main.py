from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .config.database import engine, Base
from .api.routes import servers, backups, jobs, stats, audit, auth, auth_providers
from .models import server, backup_config, backup_job, audit_log, user, auth_provider  # noqa

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IdM Backup Manager", version="2.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(servers.router,        prefix="/api/v1/servers",   tags=["servers"])
app.include_router(backups.router,        prefix="/api/v1/backups",   tags=["backups"])
app.include_router(jobs.router,           prefix="/api/v1/jobs",      tags=["jobs"])
app.include_router(stats.router,          prefix="/api/v1/stats",     tags=["stats"])
app.include_router(audit.router,          prefix="/api/v1/audit",     tags=["audit"])
app.include_router(auth.router,           prefix="/api/v1/auth",      tags=["auth"])
app.include_router(auth_providers.router, prefix="/api/v1/providers", tags=["providers"])

@app.get("/health")
@app.get("/health/")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}
