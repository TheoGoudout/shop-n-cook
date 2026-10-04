#!/usr/bin/env bash
# Write the release's per-target results to the run summary.
#
# TAG, ENVIRONMENTS and the four *_RESULT values come from the calling step's
# env, which runs `if: always()` — so any result may be `skipped` or `failure`.
# Each environment's own deploy writes its detailed summary.
set -euo pipefail

{
  echo "## Release ${TAG}"
  echo
  echo "| Target | Result |"
  echo "| --- | --- |"
  echo "| Browser extensions | ${EXTENSION_RESULT} |"
  echo "| App stores | ${STORES_RESULT} |"
  echo "| Backend image | ${IMAGES_RESULT} |"
  echo "| Deploy to ${ENVIRONMENTS} (Coolify, then Cloudflare) | ${DEPLOY_RESULT} |"
} >> "$GITHUB_STEP_SUMMARY"
