#!/bin/sh
# IDM Toolkit nginx entrypoint
# Selects HTTP or HTTPS config at startup, then polls for a .reload
# trigger written by the backend when a new SSL certificate is imported.

SSL_DIR="/etc/ssl/idm-toolkit"
HTTP_CONF="/etc/nginx/http.conf"
SSL_CONF="/etc/nginx/ssl.conf"
ACTIVE_CONF="/etc/nginx/conf.d/app.conf"
RELOAD_TRIGGER="${SSL_DIR}/.reload"

configure() {
    if [ -f "${SSL_DIR}/server.crt" ] && [ -f "${SSL_DIR}/server.key" ]; then
        echo "[entrypoint] SSL certs present — using HTTPS config"
        cp "${SSL_CONF}" "${ACTIVE_CONF}"
    else
        echo "[entrypoint] No SSL certs — using HTTP config"
        cp "${HTTP_CONF}" "${ACTIVE_CONF}"
    fi
}

# Apply the right config before nginx starts
configure

# Start nginx in the background so we can run the polling loop
nginx -g "daemon off;" &
NGINX_PID=$!

# Forward SIGTERM/INT to nginx for graceful shutdown
_term() {
    echo "[entrypoint] Shutting down nginx (pid ${NGINX_PID})"
    nginx -s quit
    wait "${NGINX_PID}"
    exit 0
}
trap _term TERM INT

echo "[entrypoint] Watching for SSL reload trigger..."
while kill -0 "${NGINX_PID}" 2>/dev/null; do
    # sleep in background so SIGTERM wakes us immediately
    sleep 5 &
    wait $!

    if [ -f "${RELOAD_TRIGGER}" ]; then
        echo "[entrypoint] Reload trigger detected — reconfiguring nginx"
        configure
        if nginx -t 2>/dev/null; then
            nginx -s reload
            echo "[entrypoint] nginx reloaded — now serving HTTPS"
        else
            echo "[entrypoint] ERROR: nginx config test failed, not reloading"
        fi
        rm -f "${RELOAD_TRIGGER}"
    fi
done

echo "[entrypoint] nginx exited"
