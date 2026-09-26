#!/usr/bin/env bash
# Abort a canary: 100% back to stable, canary container removed. Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
cp Caddyfile.stable Caddyfile
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile || true
docker compose --profile canary rm -sf site-canary || true
sed -i "s/^SITE_CANARY_TAG=.*/SITE_CANARY_TAG=/" .env
echo "✔ rolled back: 100% stable"
