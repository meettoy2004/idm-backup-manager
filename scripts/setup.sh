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
