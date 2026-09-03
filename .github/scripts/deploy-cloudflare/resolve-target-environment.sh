#!/usr/bin/env bash
# Decide which environment this run deploys to, and refuse anything else.
#
# The push trigger carries no input at all, and staging is what a push to master
# means. workflow_call and workflow_dispatch both set one. Validating it here
# rather than trusting it downstream matters because the value goes on to select
# a GitHub environment and a wrangler --env: a typo would otherwise deploy the
# staging build to a Worker environment that does not exist, or worse, resolve
# to the top-level (production) configuration.
#
# INPUT_ENVIRONMENT comes from the calling step's env, empty on a push.
set -euo pipefail

ENVIRONMENT="${INPUT_ENVIRONMENT:-staging}"
case "$ENVIRONMENT" in
  staging | production) ;;
  *)
    echo "::error::Unknown environment '$ENVIRONMENT'."
    exit 1
    ;;
esac

echo "environment=$ENVIRONMENT" >> "$GITHUB_OUTPUT"
echo "Deploying to $ENVIRONMENT"
