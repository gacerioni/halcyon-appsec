#!/usr/bin/env bash
# Start a canary of the owner portal at TAG and shift 10% of traffic to it.
#   ./canary.sh 5.4.0
# Steps: pull image -> start site-canary -> wait healthy -> smoke test pinned to canary -> Caddy 9:1.
# Fails closed: any error leaves 100% on stable.
set -euo pipefail
cd "$(dirname "$0")"
TAG="${1:?usage: canary.sh <image-tag>}"
source .env
export SITE_CANARY_TAG="$TAG"

sed -i "s/^SITE_CANARY_TAG=.*/SITE_CANARY_TAG=$TAG/" .env
echo "▶ pulling ghcr.io/$GH_OWNER/palmtree-owner-portal-bff:$TAG"
docker compose --profile canary pull -q site-canary
docker compose --profile canary up -d --no-deps site-canary

echo "▶ waiting for canary health"
for i in $(seq 1 30); do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose --profile canary ps -q site-canary)")
  [ "$st" = healthy ] && break
  sleep 2
done
[ "$st" = healthy ] || { echo "✖ canary never became healthy"; ./rollback.sh; exit 1; }

echo "▶ shifting traffic: ${STABLE_WEIGHT}:${CANARY_WEIGHT} (stable:canary)"
cp Caddyfile.canary Caddyfile
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile

echo "▶ smoke test pinned to canary (X-Canary: 1)"
if ! ./smoke.sh "https://$DOMAIN" "$TAG" canary; then
  echo "✖ smoke failed, rolling back"; ./rollback.sh; exit 1
fi
echo "✔ canary $TAG live at ${CANARY_WEIGHT}0% . Promote with ./promote.sh, abort with ./rollback.sh"
