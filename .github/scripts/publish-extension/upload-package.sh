#!/usr/bin/env bash
# Upload the packaged zip to the Chrome Web Store item.
#
# EXTENSION_ID and TOKEN come from the calling step's env.
set -euo pipefail

curl -sf -X PUT \
  "https://www.googleapis.com/upload/chromewebstore/v1.1/items/${EXTENSION_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-api-version: 2" \
  -T extension.zip
