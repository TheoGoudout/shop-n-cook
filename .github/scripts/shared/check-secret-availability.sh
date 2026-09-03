#!/usr/bin/env bash
# Turn "is this store configured?" into step outputs the publish jobs gate on.
#
# Each argument is `<output-name>=<ENV_VAR>`, and the output is `true` when that
# variable is non-empty. A missing store secret skips that publisher rather than
# failing the release: an unpublished browser extension is a missing
# nice-to-have. deploy-coolify.yml deliberately does the opposite, because a
# backend that silently did not deploy is a frontend talking to the wrong API.
#
# The variables themselves come from the calling step's env — never from the
# argument list, which would put a secret in this process's argv.
set -euo pipefail

for pair in "$@"; do
  name=${pair%%=*}
  # `A+B` means both are required — the Android publish needs a keystore *and*
  # a Play service account, and either one alone gets it nowhere.
  vars=${pair#*=}
  available=true
  missing=""
  for var in ${vars//+/ }; do
    if [ -z "${!var:-}" ]; then
      available=false
      missing="${missing} ${var}"
    fi
  done

  echo "${name}=${available}" >> "$GITHUB_OUTPUT"
  if [ "$available" != "true" ]; then
    echo "${name}: no${missing}, skipping."
  fi
done
