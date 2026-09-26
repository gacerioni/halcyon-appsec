#!/usr/bin/env bash
# Smoke test: ./smoke.sh <base-url> <expected-version> [canary]
# Checks /healthz version+color, homepage renders, /owner exists and the BFF session flow works.
set -euo pipefail
BASE="${1:?base url}"; WANT="${2:?expected version}"; TARGET="${3:-stable}"
H=(); [ "$TARGET" = canary ] && H=(-H "X-Canary: 1")
c() { curl -fsS --max-time 10 "${H[@]}" "$@"; }

hz=$(c "$BASE/healthz")
echo "$hz" | grep -q "\"version\":\"$WANT\"" || { echo "healthz version mismatch: $hz"; exit 1; }
echo "$hz" | grep -q "\"color\":\"$TARGET\"" || { echo "healthz color mismatch: $hz"; exit 1; }
c "$BASE/" | grep -qi "palm tree" || { echo "homepage missing brand"; exit 1; }
c -o /dev/null -w '%{http_code}' "$BASE/owner" | grep -q '^200$' || { echo "/owner not 200"; exit 1; }
tok=$(c -X POST "$BASE/session" -H 'content-type: application/json' \
  -d '{"ownerId":"smoke","vins":["PTM0000000000001"],"region":"NA"}' | sed -E 's/.*"token":"([^"]+)".*/\1/')
[ -n "$tok" ] || { echo "no session token"; exit 1; }
c "$BASE/vehicles/PTM0000000000001" -H "authorization: Bearer $tok" >/dev/null || { echo "vehicle summary failed"; exit 1; }
echo "✔ smoke ok: $TARGET $WANT"
