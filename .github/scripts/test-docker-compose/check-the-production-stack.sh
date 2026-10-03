#!/usr/bin/env bash
# Check the production stack does its job, from inside the containers:
# compose.yml publishes no ports, because Coolify's proxy routes to them.
#
# `up --wait` has already waited for the API's healthcheck; this asserts it
# again so a failure names the service, and covers prestart, which is a one-shot
# container with no healthcheck of its own.
set -euo pipefail

compose() { docker compose -f compose.yml "$@"; }

echo "API:"
compose exec -T backend curl -fsS http://localhost:8000/api/v1/utils/health-check/
echo

# Migrations ran and the first superuser exists: the prestart service is what
# Coolify relies on for both, on every deploy.
echo "Prestart:"
CODE=$(docker inspect -f '{{.State.ExitCode}}' "$(compose ps -a -q prestart)")
if [ "$CODE" != "0" ]; then
  echo "::error::prestart exited with ${CODE}."
  compose logs prestart
  exit 1
fi
echo "completed"
