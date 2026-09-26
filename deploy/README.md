# Demo host: cognition.platformengineer.io

One Compute Engine VM (Ubuntu 24.04, e2-small is enough), Docker Compose, Caddy with Let's Encrypt.

```
cognition.platformengineer.io/        Palm Tree Motors site   (image: ghcr.io/gacerioni/palmtree-owner-portal-bff)
cognition.platformengineer.io/ops/    Remediation Command Center (static, from dashboard/)
```

## First time (≈10 min)

1. GCP: create the VM, allow **tcp/80 + tcp/443** in its firewall, note the external IP (reserve it as static).
2. GoDaddy: **A record** `cognition` → that IP. Wait for `dig +short cognition.platformengineer.io` to answer.
3. On the VM:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/gacerioni/palmtree-appsec/main/deploy/bootstrap.sh | bash
   newgrp docker
   cd ~/palmtree-appsec/deploy && cp .env.example .env && $EDITOR .env   # DOMAIN, ACME_EMAIL, SITE_STABLE_TAG
   docker compose up -d --build
   ```
   Caddy gets the certificate on first request. `docker compose logs -f caddy` if it does not.
4. GitHub → repo `palmtree-owner-portal-bff` → Settings → Secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
   (a dedicated `deploy` user on the VM, key-only, in the `docker` group). Settings → Environments → `production`
   → **Required reviewers: you**. That click is the "human approves the release" moment in the demo.

## Every demo day

```bash
make dashboard            # locally: refresh dashboard/data.json, then
make ops-deploy           # scp it to the VM and rebuild the ops container
```

## The canary, by hand (what the workflow does)

```bash
./canary.sh 5.4.0-abc1234   # pull, start canary, wait healthy, Caddy 9:1, smoke pinned to canary
./promote.sh                # stable takes the new tag, canary removed, smoke on stable
./rollback.sh               # any time: 100% stable
```

Watch it: reload the site footer badge (`vX · stable` / `vY · canary`), or `for i in $(seq 20); do curl -s https://$DOMAIN/healthz; echo; done`.
`curl -H 'X-Canary: 1' https://$DOMAIN/healthz` pins to the canary.

Nothing here has credentials. `.env` stays on the VM (gitignored).
