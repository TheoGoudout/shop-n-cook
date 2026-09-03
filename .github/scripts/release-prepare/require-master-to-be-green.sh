#!/usr/bin/env bash
# Refuse to cut a release from a master that CI has not blessed.
#
# GH_TOKEN and REPOSITORY come from the calling step's env.
set -euo pipefail

SHA=$(git rev-parse HEAD)

# Keyed on workflow file paths rather than check-run names, which are job names
# and drift (test-extension.yml's job is "Test & Build Extension").
# deploy-cloudflare is deliberately absent: a staging deploy hiccup should not
# block cutting a release.
REQUIRED="test-backend.yml playwright.yml test-extension.yml test-docker-compose.yml"

FAILED=0
AT_HEAD=0

for workflow in $REQUIRED; do
  RUNS=$(gh api \
    "repos/${REPOSITORY}/actions/workflows/${workflow}/runs?branch=master&per_page=20" \
    --jq '.workflow_runs[] | [.head_sha, .status, .conclusion] | @tsv')

  LINE=$(echo "$RUNS" | awk -F'\t' -v s="$SHA" '$1 == s {print; exit}')
  if [ -n "$LINE" ]; then
    AT_HEAD=$((AT_HEAD + 1))
    SCOPE="on $SHA"
  else
    # test-extension.yml is path-filtered to extension/**, so it legitimately
    # does not run for commits that touch nothing there. Its last completed run
    # on master is still the current truth about that subsystem, so fall back to
    # it rather than treating "did not run" as "not green".
    LINE=$(echo "$RUNS" | awk -F'\t' '$2 == "completed" {print; exit}')
    SCOPE="on master (not triggered by $SHA)"
  fi

  if [ -z "$LINE" ]; then
    echo "::warning::${workflow} has never completed a run on master; skipping it."
    continue
  fi

  STATUS=$(echo "$LINE" | cut -f2)
  CONCLUSION=$(echo "$LINE" | cut -f3)
  if [ "$STATUS" != "completed" ]; then
    echo "::error::${workflow} is still ${STATUS} ${SCOPE}."
    FAILED=1
  elif [ "$CONCLUSION" != "success" ] && [ "$CONCLUSION" != "skipped" ]; then
    echo "::error::${workflow} concluded '${CONCLUSION}' ${SCOPE}."
    FAILED=1
  else
    echo "${workflow}: ${CONCLUSION} ${SCOPE}."
  fi
done

# Guarantees the commit being released actually got CI, rather than every
# required workflow silently falling back to an older run.
if [ "$AT_HEAD" = "0" ]; then
  echo "::error::No required workflow ran against ${SHA} at all."
  FAILED=1
fi

if [ "$FAILED" = "1" ]; then
  echo "::error::master is not green — refusing to release."
  exit 1
fi
echo "master is green at ${SHA}."
