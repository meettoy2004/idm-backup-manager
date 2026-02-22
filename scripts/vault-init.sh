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
