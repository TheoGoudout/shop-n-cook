#!/usr/bin/env bash
# Sign the add-on and submit it to addons.mozilla.org.
#
# API_KEY and API_SECRET come from the calling step's env. They used to be
# interpolated onto this command line, which put both secrets in the process's
# argv — readable by anything else on the runner, and preserved by any `set -x`.
set -euo pipefail

# Always "listed" (appears publicly on addons.mozilla.org): the job's `if`
# already excludes pre-releases, so the unlisted path was unreachable. RC
# testers install extension.zip directly in Firefox Dev Edition instead.
CHANNEL=listed

web-ext sign \
  --source-dir ext-src \
  --channel "$CHANNEL" \
  --api-key "$API_KEY" \
  --api-secret "$API_SECRET" \
  --artifacts-dir /tmp/web-ext-artifacts

echo "channel=${CHANNEL}" >> "$GITHUB_OUTPUT"
