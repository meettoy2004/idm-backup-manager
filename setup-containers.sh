#!/usr/bin/env bash
# Run this script from ~/idm-backup-manager
# It writes every containerization file in place.
# Usage: bash setup-containers.sh

set -e
cd ~/idm-backup-manager

echo "==> Creating directory structure..."
mkdir -p scripts k8s/base k8s/overlays/dev k8s/overlays/prod

# ─────────────────────────────────────────────────────────────────────────────
# BACKEND requirements.txt  (replaces the incomplete one)
# ─────────────────────────────────────────────────────────────────────────────
cat > backend/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.36
alembic==1.13.3
psycopg2-binary==2.9.10
pydantic==2.9.2
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
httpx==0.27.2
paramiko==3.5.0
ldap3==2.9.1
hvac==2.3.0
redis==5.2.0
cryptography==43.0.3
python-dotenv==1.0.1
jinja2==3.1.4
EOF

# ─────────────────────────────────────────────────────────────────────────────
# BACKEND Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
cat > backend/Dockerfile << 'EOF'
# Stage 1: builder
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libffi-dev libssl-dev openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 openssh-client curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
COPY . .
RUN mkdir -p /app/alembic/versions && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/stats/overview || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
EOF

# ─────────────────────────────────────────────────────────────────────────────
# BACKEND .dockerignore
# ─────────────────────────────────────────────────────────────────────────────
cat > backend/.dockerignore << 'EOF'
__pycache__
*.pyc
*.pyo
.venv
venv
.env
.env.*
*.log
.git
.pytest_cache
htmlcov
.coverage
EOF

# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
cat > frontend/Dockerfile << 'EOF'
# Stage 1: build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --silent
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:1.27-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/app.conf
COPY --from=builder /app/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html \
 && chown -R nginx:nginx /var/cache/nginx \
 && chown -R nginx:nginx /var/log/nginx \
 && touch /var/run/nginx.pid \
 && chown -R nginx:nginx /var/run/nginx.pid
USER nginx
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
EOF

# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND nginx.conf  (lives beside the Dockerfile)
# ─────────────────────────────────────────────────────────────────────────────
cat > frontend/nginx.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1024;

    # Proxy /api/ calls to backend — eliminates CORS in production
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

    # React SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health probe
    location /health {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
EOF

# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND .dockerignore
# ─────────────────────────────────────────────────────────────────────────────
cat > frontend/.dockerignore << 'EOF'
node_modules
dist
.env
.env.*
*.log
.git
EOF

# ─────────────────────────────────────────────────────────────────────────────
# VITE CONFIG — make VITE_API_URL injectable
# ─────────────────────────────────────────────────────────────────────────────
cat > frontend/vite.config.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5174,
    // Dev proxy — matches nginx proxy_pass in production
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 5174,
  }
})
EOF

# ─────────────────────────────────────────────────────────────────────────────
# docker-compose.yml  (root of project)
# ─────────────────────────────────────────────────────────────────────────────
cat > docker-compose.yml << 'EOF'
version: "3.9"

# Usage:
#   Dev:         docker compose up
#   Production:  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
#   First run:   docker compose exec backend alembic upgrade head
#                docker compose exec backend python -c "
#                  import httpx; r=httpx.post('http://localhost:8000/api/v1/auth/bootstrap'); print(r.text)"

x-logging: &logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

services:

  postgres:
    image: postgres:16-alpine
    container_name: idm-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER:     ${POSTGRES_USER:-idm}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-idm_dev_password}
      POSTGRES_DB:       ${POSTGRES_DB:-idm_backup}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-idm} -d ${POSTGRES_DB:-idm_backup}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    logging: *logging
    networks: [idm-net]

  redis:
    image: redis:7-alpine
    container_name: idm-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis_dev_password} --appendonly yes
    volumes:
      - redisdata:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "--no-auth-warning", "-a", "${REDIS_PASSWORD:-redis_dev_password}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging: *logging
    networks: [idm-net]

  vault:
    image: hashicorp/vault:1.17
    container_name: idm-vault
    restart: unless-stopped
    cap_add: [IPC_LOCK]
    environment:
      VAULT_DEV_ROOT_TOKEN_ID:  ${VAULT_TOKEN:-dev-root-token}
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
      VAULT_LOG_LEVEL:          warn
    ports:
      - "${VAULT_PORT:-8200}:8200"
    volumes:
      - vaultdata:/vault/data
      - vaultlogs:/vault/logs
    healthcheck:
      test: ["CMD", "vault", "status", "-address=http://127.0.0.1:8200"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s
    logging: *logging
    networks: [idm-net]

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: idm-backend
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-idm}:${POSTGRES_PASSWORD:-idm_dev_password}@postgres:5432/${POSTGRES_DB:-idm_backup}
      REDIS_URL:    redis://:${REDIS_PASSWORD:-redis_dev_password}@redis:6379/0
      VAULT_ADDR:   http://vault:8200
      VAULT_TOKEN:  ${VAULT_TOKEN:-dev-root-token}
      APP_ENV:      ${APP_ENV:-development}
      DEBUG:        ${DEBUG:-true}
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    volumes:
      - ${SSH_KEY_PATH:-~/.ssh}:/home/appuser/.ssh:ro
    depends_on:
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
      vault:    { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/stats/overview"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging: *logging
    networks: [idm-net]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_URL: ${VITE_API_URL:-http://localhost:8000}
    container_name: idm-frontend
    restart: unless-stopped
    ports:
      - "${FRONTEND_PORT:-5174}:80"
    depends_on:
      backend: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:80/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging: *logging
    networks: [idm-net]

volumes:
  pgdata:
  redisdata:
  vaultdata:
  vaultlogs:

networks:
  idm-net:
    driver: bridge
    name: idm-network
EOF

# ─────────────────────────────────────────────────────────────────────────────
# docker-compose.prod.yml
# ─────────────────────────────────────────────────────────────────────────────
cat > docker-compose.prod.yml << 'EOF'
version: "3.9"
# Production overrides
# Usage: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

services:
  postgres:
    ports: []  # no external exposure
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}

  redis:
    ports: []
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD:?Set REDIS_PASSWORD}
      --appendonly yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru

  vault:
    ports: []

  backend:
    volumes:
      - ${SSH_KEY_PATH:-/opt/idm-backup/ssh}:/home/appuser/.ssh:ro
    environment:
      APP_ENV:    production
      DEBUG:      "false"
      SECRET_KEY: ${SECRET_KEY:?Set SECRET_KEY}
      DATABASE_URL: postgresql://${POSTGRES_USER:-idm}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-idm_backup}
      REDIS_URL:    redis://:${REDIS_PASSWORD}@redis:6379/0
      VAULT_TOKEN:  ${VAULT_TOKEN:?Set VAULT_TOKEN}
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log

  frontend:
    # In production, nginx proxies /api/ so VITE_API_URL is empty (same origin)
    build:
      args:
        VITE_API_URL: ""
EOF

# ─────────────────────────────────────────────────────────────────────────────
# .env.example
# ─────────────────────────────────────────────────────────────────────────────
cat > .env.example << 'EOF'
# Copy to .env and fill in — never commit .env

# App
APP_ENV=development
DEBUG=true
SECRET_KEY=change-this-run-openssl-rand-hex-32

# Postgres
POSTGRES_USER=idm
POSTGRES_PASSWORD=idm_dev_password
POSTGRES_DB=idm_backup
POSTGRES_PORT=5432

# Redis
REDIS_PASSWORD=redis_dev_password
REDIS_PORT=6379

# Vault
VAULT_TOKEN=dev-root-token
VAULT_PORT=8200

# Ports
BACKEND_PORT=8000
FRONTEND_PORT=5174

# Frontend API URL (dev: backend URL; prod: leave empty for nginx proxy)
VITE_API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5174

# Bootstrap admin (first-run only)
BOOTSTRAP_ADMIN_EMAIL=admin@local
BOOTSTRAP_ADMIN_PASSWORD=changeme123

# SSH keys path on host (mounted into backend container)
SSH_KEY_PATH=~/.ssh
EOF

# ─────────────────────────────────────────────────────────────────────────────
# .gitignore additions
# ─────────────────────────────────────────────────────────────────────────────
cat > .gitignore << 'EOF'
.env
.env.*
!.env.example
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.log
.DS_Store
node_modules/
frontend/dist/
backend/htmlcov/
backend/.coverage
*.egg-info/
EOF

# ─────────────────────────────────────────────────────────────────────────────
# scripts/init-db.sql
# ─────────────────────────────────────────────────────────────────────────────
cat > scripts/init-db.sql << 'EOF'
-- Runs once on first postgres container start
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
GRANT ALL PRIVILEGES ON DATABASE idm_backup TO idm;
EOF

# ─────────────────────────────────────────────────────────────────────────────
# scripts/vault-init.sh
# ─────────────────────────────────────────────────────────────────────────────
cat > scripts/vault-init.sh << 'EOF'
#!/bin/sh
set -e
VAULT_ADDR=${VAULT_ADDR:-http://127.0.0.1:8200}
VAULT_TOKEN=${VAULT_TOKEN:-dev-root-token}

echo "Waiting for Vault..."
until vault status -address="$VAULT_ADDR" > /dev/null 2>&1; do sleep 2; done

echo "Enabling KV v2..."
vault secrets enable -address="$VAULT_ADDR" -path=secret kv-v2 2>/dev/null || echo "KV already enabled"

vault kv put -address="$VAULT_ADDR" secret/backup-keys/.init initialized=true
vault kv put -address="$VAULT_ADDR" secret/ssh-keys/.init   initialized=true

echo "Vault init done."
EOF
chmod +x scripts/vault-init.sh

# ─────────────────────────────────────────────────────────────────────────────
# scripts/setup.sh  — first-time bootstrap helper
# ─────────────────────────────────────────────────────────────────────────────
cat > scripts/setup.sh << 'EOF'
#!/usr/bin/env bash
# First-time setup: runs migrations and bootstraps admin user
set -e
cd "$(dirname "$0")/.."

echo "==> Waiting for backend to be healthy..."
until curl -sf http://localhost:8000/api/v1/stats/overview > /dev/null 2>&1; do
  echo "   waiting..."; sleep 3
done

echo "==> Running database migrations..."
docker compose exec backend alembic upgrade head

echo "==> Initialising Vault KV engine..."
docker compose exec vault sh /vault-init.sh

echo "==> Bootstrapping admin user..."
curl -s -X POST http://localhost:8000/api/v1/auth/bootstrap | python3 -m json.tool

echo ""
echo "==> Setup complete!"
echo "    Frontend: http://localhost:${FRONTEND_PORT:-5174}"
echo "    Backend:  http://localhost:${BACKEND_PORT:-8000}/docs"
echo "    Vault UI: http://localhost:${VAULT_PORT:-8200}"
echo "    Login:    admin / changeme123  (change this now)"
EOF
chmod +x scripts/setup.sh

# ─────────────────────────────────────────────────────────────────────────────
# alembic.ini  — update sqlalchemy.url to use env var
# ─────────────────────────────────────────────────────────────────────────────
# Only patch if alembic.ini exists
if [ -f backend/alembic.ini ]; then
  sed -i.bak 's|sqlalchemy\.url = postgresql://.*|sqlalchemy.url = %(DATABASE_URL)s|' backend/alembic.ini
  echo "==> Patched alembic.ini to use %(DATABASE_URL)s"
fi

# ─────────────────────────────────────────────────────────────────────────────
# alembic/env.py  — wire DATABASE_URL from settings
# ─────────────────────────────────────────────────────────────────────────────
cat > backend/alembic/env.py << 'EOF'
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config.database import Base
from app.models import *  # noqa: F401,F403 — ensure all models are imported

config = context.config

# Override sqlalchemy.url with DATABASE_URL env var (used in Docker)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
EOF

echo ""
echo "======================================================"
echo " All files written. Next steps:"
echo ""
echo "   1. cp .env.example .env"
echo "   2. Edit .env (set SECRET_KEY, passwords)"
echo "   3. docker compose up --build -d"
echo "   4. bash scripts/setup.sh"
echo ""
echo " Production:"
echo "   docker compose -f docker-compose.yml \\"
echo "     -f docker-compose.prod.yml up --build -d"
echo "======================================================"
