#!/usr/bin/env bash
# Run the E2E reports (`pytest -m e2e`) on the VPS, in a throwaway container of the deployed image (plan2 rozdz. 3, W).
#   deploy/e2e-vps.sh root@129.121.162.156 -k 2019     -> historical date only (6 cases; the default for gates)
#   deploy/e2e-vps.sh root@129.121.162.156             -> all 12 cases, compared with backend/tests/e2e/baseline.json
#   deploy/e2e-vps.sh root@129.121.162.156 --update    -> also rewrite baseline.json (copied back here)
# Arguments after the host (and --update) go to pytest unchanged.
# Use it when the local address is throttled (ULDK redirects, Open-Meteo "Daily API request limit exceeded"; see
# docs/DATA_SOURCES.md). The tests are those of this working tree; the app code is the image deployed on the VPS,
# so deploy first. Every case is a cold analysis from the production address and uses part of its daily Open-Meteo
# quota and ULDK allowance: prefer `-k 2019`, and do not run it right before a demo.
set -euo pipefail
TARGET="${1:?usage: deploy/e2e-vps.sh user@host [--update] [pytest args...]}"
shift
UPDATE=""
if [[ "${1:-}" == "--update" ]]; then
  UPDATE="--update"
  shift
fi
REMOTE=/tmp/rsw-e2e
CONTAINER=rsw-e2e
cd "$(dirname "$0")/../backend"

# Ctrl-C or a dropped connection must not leave the container running next to production (2 GB RAM).
cleanup() {
  ssh "$TARGET" "docker rm -f $CONTAINER >/dev/null 2>&1; rm -rf $REMOTE" || true
}
trap cleanup EXIT

# pytest arguments travel as NUL-separated base64, so no quoting survives two remote shells by accident.
ARGS_B64="$( (for arg in "$@"; do printf '%s\0' "$arg"; done) | base64 | tr -d '\n')"

tar --exclude __pycache__ -cf - tests pyproject.toml | ssh "$TARGET" \
  "rm -rf $REMOTE && mkdir -p $REMOTE && tar -x -C $REMOTE && chmod -R a+rwX $REMOTE \
   && printf '%s' '$ARGS_B64' | base64 -d > $REMOTE/args"

ENV_ARGS=""
[[ "$UPDATE" == "--update" ]] && ENV_ARGS="-e RSW_E2E_UPDATE_BASELINE=1"
status=0
# Versions as in backend/requirements-dev.txt.
ssh "$TARGET" "docker rm -f $CONTAINER >/dev/null 2>&1; docker run --rm --init --name $CONTAINER --memory 900m \
  -e HOME=/tmp $ENV_ARGS -v $REMOTE/tests:/app/backend/tests -v $REMOTE/pyproject.toml:/app/backend/pyproject.toml \
  -v $REMOTE/args:/tmp/pytest-args:ro rolnikszukawody:latest sh -c 'pip install -q --user --no-warn-script-location \
    pytest==9.2.0 pytest-asyncio==1.5.0 respx==0.23.1 && \
    xargs -0 -a /tmp/pytest-args python -m pytest -p no:cacheprovider -m e2e tests/e2e/test_reports.py -q -s'" \
  || status=$?

if [[ "$UPDATE" == "--update" ]]; then
  scp -q "$TARGET:$REMOTE/tests/e2e/baseline.json" tests/e2e/baseline.json && echo "baseline.json updated"
fi
exit $status
