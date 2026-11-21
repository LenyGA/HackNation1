#!/usr/bin/env bash
# Deploy the committed main branch to the VPS (run on your machine, from the repo root).
#   deploy/deploy.sh root@129.121.162.156                  -> https://129.121.162.156.sslip.io
#   deploy/deploy.sh root@129.121.162.156 moja.domena.pl   -> https://moja.domena.pl (DNS A record -> VPS first)
# sslip.io is a public name that resolves to the IP inside it, so Caddy gets a real HTTPS certificate even
# before a domain exists. The image is built on the VPS (it is x86_64; laptops are often arm64).
set -euo pipefail
TARGET="${1:?usage: deploy/deploy.sh user@host [domain]}"
HOST="${TARGET#*@}"
DIR=/opt/rolnikszukawody

if [[ $# -ge 2 ]]; then
  DOMAIN="$2"
elif [[ "$HOST" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then
  DOMAIN="${HOST}.sslip.io"
else
  echo "Give the domain as the second argument (host '$HOST' is not an IPv4 address)." >&2
  exit 1
fi
if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "Invalid domain: $DOMAIN" >&2
  exit 1
fi

# Only what is committed on main is deployed (git archive HEAD), so refuse anything else.
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Not on main; deploy only from main." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Uncommitted changes would not be deployed. Commit (and push) first:" >&2
  git status --short >&2
  exit 1
fi

echo "Deploying $(git rev-parse --short HEAD) to $TARGET as https://$DOMAIN"
# Fresh copy of the tree (files deleted from the repo disappear too); .env and Docker volumes are kept.
git archive --format=tar HEAD | ssh "$TARGET" \
  "mkdir -p $DIR && find $DIR -mindepth 1 -maxdepth 1 ! -name .env -exec rm -rf {} + && tar -x -C $DIR"
# SITE_ADDRESS is set (or updated) in .env; any other variables there are left alone.
ssh "$TARGET" "cd $DIR && touch .env && sed -i '/^SITE_ADDRESS=/d' .env && echo 'SITE_ADDRESS=$DOMAIN' >> .env \
  && docker compose up -d --build && docker image prune -f >/dev/null"

echo "Waiting for the app..."
for _ in $(seq 1 60); do
  if curl -fsS "https://$DOMAIN/api/health" >/dev/null 2>&1; then
    echo "OK: https://$DOMAIN"
    ssh "$TARGET" "cd $DIR && docker compose exec -T app python scripts/warm_cache.py" \
      || echo "Cache warm-up had errors (see above)."
    exit 0
  fi
  sleep 5
done
echo "Health check failed; logs: ssh $TARGET 'cd $DIR && docker compose logs --tail 50'" >&2
exit 1
