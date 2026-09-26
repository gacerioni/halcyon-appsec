#!/usr/bin/env bash
# Promote the running canary to 100%: stable takes the canary tag, canary container is removed.
set -euo pipefail
cd "$(dirname "$0")"
source .env
[ -n "${SITE_CANARY_TAG:-}" ] || { echo "no canary to promote"; exit 1; }
echo "▶ promoting $SITE_CANARY_TAG (was $SITE_STABLE_TAG)"
sed -i "s/^SITE_STABLE_TAG=.*/SITE_STABLE_TAG=$SITE_CANARY_TAG/" .env
# keep serving from the canary while stable restarts on the new image
cp Caddyfile.canary Caddyfile
docker compose up -d --no-deps site-stable
for i in $(seq 1 30); do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q site-stable)"); [ "$st" = healthy ] && break; sleep 2
done
[ "$st" = healthy ] || { echo "✖ new stable unhealthy"; exit 1; }
cp Caddyfile.stable Caddyfile
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
docker compose --profile canary rm -sf site-canary
sed -i "s/^SITE_CANARY_TAG=.*/SITE_CANARY_TAG=/" .env
./smoke.sh "https://$DOMAIN" "$SITE_CANARY_TAG" stable
echo "✔ $SITE_CANARY_TAG is now 100% stable"
