# IdM Backup Manager

A full-stack web application for managing, monitoring, and restoring Identity Management (IdM) server backups. Built with FastAPI, React, Celery, and PostgreSQL — deployable via Docker Compose or Kubernetes.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Services](#services)
- [Database Migrations](#database-migrations)
- [API](#api)
- [Development](#development)
- [Production Deployment](#production-deployment)
- [Kubernetes](#kubernetes)

---

## Overview

IdM Backup Manager provides a centralized dashboard to:

- Schedule and monitor backups across multiple IdM servers via SSH + systemd timers
- Track job history (status, duration, size) pulled from systemd journal
- Manage users with role-based access control (Admin / Editor / Viewer)
- Authenticate via Local credentials, OIDC, LDAP, or SAML
- Encrypt backups with GPG (Vault-managed keys)
- Restore backups through a guided multi-step wizard
- Receive email/Slack alerts on backup failures
- Generate weekly and monthly reports

---

## Architecture

```
┌──────────────┐     HTTP      ┌─────────────────┐
│   Browser    │ ◄──────────► │  Nginx (React)  │  :5174
└──────────────┘               └────────┬────────┘
                                        │ proxy /api
                               ┌────────▼────────┐
                               │ FastAPI Backend  │  :8000
                               └──┬──────────┬───┘
                                  │          │
                          ┌───────▼──┐  ┌────▼──────┐
                          │ Postgres │  │   Redis   │
                          │  :5432   │  │   :6379   │
                          └──────────┘  └─────┬─────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │  Celery Worker/Beat  │
                                   │  (periodic polling,  │
                                   │   notifications,     │
                                   │   reports)           │
                                   └──────────────────────┘
                                              │ SSH
                                   ┌──────────▼──────────┐
                                   │   IdM Servers        │
                                   │  (systemd timers)    │
                                   └──────────────────────┘
```

**Stack:**

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.115, Python 3.11 |
| ORM / Migrations | SQLAlchemy 2.0, Alembic 1.13 |
| Task Queue | Celery 5.4 + Redis 7 |
| Database | PostgreSQL 16 |
| Secrets | HashiCorp Vault 1.17 |
| SSH | Paramiko 3.5 |
| Frontend | React 19, Vite 7, Recharts |
| Auth | JWT, OIDC, LDAP, SAML |

---

## Features

- **Multi-server management** — add, edit, and monitor any number of IdM servers
- **Automated scheduling** — generate and deploy systemd timers via SSH
- **Job history** — pull 30–90 days of backup history from the systemd journal
- **Real-time dashboard** — success rate, backup duration, and failure charts
- **RBAC** — Admin, Editor, and Viewer roles with per-route enforcement
- **Multi-auth** — Local, OIDC, LDAP, and SAML authentication
- **Audit logging** — full trail of user actions with IP and timestamp
- **GPG encryption** — Vault-managed keys for backup encryption
- **Backup verification** — GPG signature and integrity checks
- **Restore wizard** — guided multi-step restore with progress tracking
- **Email / Slack notifications** — configurable failure and success alerts
- **Multi-tenancy** — organization-based resource scoping
- **DR templates** — reusable disaster-recovery playbooks
- **S3 cleanup** — automated old-backup pruning
- **Rate limiting** — SlowAPI per-endpoint throttling
- **Kubernetes ready** — full manifest in `idm-backup-k8s.yaml`

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- SSH access to target IdM servers (key-based, `backup-mgmt` user)
- (Optional) HashiCorp Vault for GPG key storage

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd idm-backup-manager

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set BOOTSTRAP_ADMIN_PASSWORD and SECRET_KEY

# 3. Build and start
docker compose build
docker compose up -d

# 4. Apply database migrations
docker compose exec backend alembic upgrade head

# 5. Open the UI
open http://localhost:5174
# Login: admin@local / <your BOOTSTRAP_ADMIN_PASSWORD>
```

---

## Configuration

All configuration is via environment variables in `.env`. See `.env.example` for the full list.

| Variable | Description | Default |
|---|---|---|
| `APP_ENV` | `development` or `production` | `development` |
| `DEBUG` | Enable debug logging | `true` |
| `SECRET_KEY` | JWT signing secret — **change in production** | — |
| `POSTGRES_USER` | Database user | `idm` |
| `POSTGRES_PASSWORD` | Database password | — |
| `POSTGRES_DB` | Database name | `idm_backup` |
| `REDIS_PASSWORD` | Redis password | — |
| `VAULT_TOKEN` | Vault root token | `dev-root-token` |
| `BOOTSTRAP_ADMIN_EMAIL` | Initial admin email | `admin@local` |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial admin password | — |
| `SSH_KEY_PATH` | Host path to SSH private keys | `~/.ssh` |
| `VITE_API_URL` | Frontend API base URL | `http://localhost:8000` |
| `CORS_ORIGINS_STR` | Allowed CORS origins (comma-separated or `*`) | `*` |
| `SMTP_HOST` | SMTP server for email notifications | — |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | — |
| `SMTP_PASSWORD` | SMTP password | — |

---

## Services

| Service | Port | Description |
|---|---|---|
| `frontend` | 5174 | React + Nginx (SPA) |
| `backend` | 8000 | FastAPI application |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis (Celery broker + cache) |
| `vault` | 8200 | HashiCorp Vault |
| `celery-worker` | — | Celery task worker |
| `celery-beat` | — | Celery periodic task scheduler |

### Health checks

```bash
# All services
docker compose ps

# Backend API
curl http://localhost:8000/api/v1/stats/overview

# Individual logs
docker compose logs -f backend
docker compose logs -f celery-worker
```

---

## Database Migrations

Migrations are managed with Alembic and are idempotent.

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Check current revision
docker compose exec backend alembic current

# Generate a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Rollback one step
docker compose exec backend alembic downgrade -1
```

### Migration history

| File | Description |
|---|---|
| `b75868ff2ec1_initial_schema.py` | Base schema (servers, backups, jobs, users, audit) |
| `20260218_add_requires_password_change.py` | Forced password-change flag on users |
| `20260219120227_add_subscription_status.py` | IdM subscription status on servers |
| `20260222_add_high_value_features.py` | Organizations, notifications, verification, restore, DR templates |
| `20260224_add_fk_indexes.py` | Foreign key index optimization |

---

## API

The backend exposes a versioned REST API at `/api/v1/`.

| Prefix | Description |
|---|---|
| `/api/v1/auth` | Login, token refresh, logout, password change |
| `/api/v1/servers` | Server CRUD + subscription check |
| `/api/v1/backups` | Backup config CRUD |
| `/api/v1/jobs` | Job listing and status |
| `/api/v1/stats` | Dashboard statistics |
| `/api/v1/users` | User management (admin) |
| `/api/v1/audit` | Audit log retrieval |
| `/api/v1/auth-providers` | OIDC / LDAP / SAML provider config |
| `/api/v1/organizations` | Organization CRUD |
| `/api/v1/notifications` | Notification settings |
| `/api/v1/verifications` | Trigger and check backup verification |
| `/api/v1/restores` | Initiate and monitor restore operations |
| `/api/v1/reports` | Generate and download reports |
| `/api/v1/dr-templates` | DR template CRUD |

Interactive Swagger docs (development only): `http://localhost:8000/docs`

---

## Development

```bash
# Start with live-reload (backend hot-reloads via uvicorn, frontend via Vite HMR)
docker compose up -d

# Rebuild after dependency changes (requirements.txt or package.json)
docker compose build backend   # or: frontend
docker compose up -d backend

# Run backend tests
docker compose exec backend pytest

# Access the database
docker compose exec postgres psql -U idm -d idm_backup

# Tail all logs
docker compose logs -f
```

### Project structure

```
idm-backup-manager/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── celery_app.py            # Celery configuration
│   │   ├── tasks.py                 # Periodic Celery tasks
│   │   ├── config/                  # Settings, database engine
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── services/                # Business logic (SSH, auth, email, restore …)
│   │   └── api/routes/              # FastAPI route handlers
│   ├── alembic/versions/            # Database migration files
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Root component and tab routing
│   │   ├── Dashboard.jsx            # Stats and charts
│   │   ├── Login.jsx
│   │   ├── Users.jsx
│   │   ├── AuditLog.jsx
│   │   ├── RestoreWizard.jsx
│   │   ├── NotificationSettings.jsx
│   │   ├── DRTemplates.jsx
│   │   └── api.js                   # Axios instance
│   ├── Dockerfile
│   └── package.json
├── scripts/
│   ├── setup.sh
│   ├── vault-init.sh
│   └── init-db.sql
├── docker-compose.yml
├── docker-compose.prod.yml
├── idm-backup-k8s.yaml              # Kubernetes manifests
├── .env.example
└── SESSION_STATE.md                 # Development session notes
```

---

## Production Deployment

```bash
# Use the production Compose override
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Recommended: set strong secrets in .env before deploying
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 24)
```

Production checklist:
- [ ] Replace all default passwords in `.env`
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Configure `CORS_ORIGINS_STR` to your actual domain(s)
- [ ] Set `VITE_API_URL` to your public API endpoint
- [ ] Configure SMTP credentials for email notifications
- [ ] Mount real SSH private keys at `SSH_KEY_PATH`
- [ ] Initialise Vault with real GPG keys
- [ ] Apply migrations: `docker compose exec backend alembic upgrade head`

---

## Kubernetes

Full Kubernetes manifests are in `idm-backup-k8s.yaml`, including:

- Namespace, ConfigMap, Secrets
- Deployments for backend, frontend, Celery worker/beat
- StatefulSets for PostgreSQL and Redis
- PersistentVolumeClaims for data durability
- Services and Ingress

```bash
kubectl apply -f idm-backup-k8s.yaml
kubectl -n idm-backup get pods
```
