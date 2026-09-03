#!/usr/bin/env bash
# Give the signed XPI the release's own name, so the asset is identifiable.
#
# web-ext names it after the manifest version, which carries no pre-release
# suffix — so two release candidates would produce the same filename.
#
# VERSION comes from the calling step's env.
set -euo pipefail

XPI=$(find /tmp/web-ext-artifacts -name "*.xpi" -print -quit)
if [ -n "$XPI" ]; then
  cp "$XPI" "shop-n-cook-${VERSION}.xpi"
else
  echo "::warning::web-ext produced no .xpi; nothing to attach."
fi
