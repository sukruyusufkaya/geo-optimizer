#!/usr/bin/env bash
# Pull, rebuild and restart GEO Optimizer Web on the server.
#
#   ssh user@server
#   cd /opt/geo-optimizer && ./deploy/deploy.sh
#
# Safe to re-run: the old container keeps serving until the new image is built.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$PWD"
COMPOSE="docker compose -f deploy/docker-compose.yml"

if [[ ! -f deploy/.env ]]; then
    echo "deploy/.env is missing — copy deploy/.env.example and fill it in." >&2
    exit 1
fi

echo "==> Fetching latest code"
git pull --ff-only

PREVIOUS=$(git rev-parse --short HEAD)
echo "==> Building image at $PREVIOUS"
# The Astro stage regenerates sitemap.xml and llms.txt from the live Sanity
# dataset and fails the build if Sanity is unreachable, so a network blip here
# stops the deploy before the running container is touched. That is the point.
$COMPOSE build

echo "==> Restarting service"
$COMPOSE up -d

echo "==> Waiting for health"
for _ in $(seq 1 30); do
    status=$(docker inspect -f '{{.State.Health.Status}}' geo-optimizer-web 2>/dev/null || echo starting)
    if [[ "$status" == "healthy" ]]; then
        echo "==> Healthy — deployed $PREVIOUS"
        $COMPOSE ps
        exit 0
    fi
    sleep 5
done

echo "Container did not become healthy in 150s. Recent logs:" >&2
$COMPOSE logs --tail 50 web >&2
exit 1
