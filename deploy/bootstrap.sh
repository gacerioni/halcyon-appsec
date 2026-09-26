#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 Compute Engine VM (run as a sudo-capable user).
#   curl -fsSL https://raw.githubusercontent.com/gacerioni/palmtree-appsec/main/deploy/bootstrap.sh | bash
set -euo pipefail
sudo apt-get update -q && sudo apt-get install -y -q ca-certificates curl git
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
[ -d ~/palmtree-appsec ] || git clone -q https://github.com/gacerioni/palmtree-appsec ~/palmtree-appsec
cd ~/palmtree-appsec/deploy
[ -f .env ] || { cp .env.example .env; echo "edit deploy/.env (DOMAIN, ACME_EMAIL, SITE_STABLE_TAG) then run: docker compose up -d --build"; }
echo "firewall: allow tcp/80 and tcp/443 on the VM; DNS: A record for \$DOMAIN -> this VM's external IP"
