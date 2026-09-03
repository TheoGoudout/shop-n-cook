#!/usr/bin/env bash
# Upload the packaged zip into the Edge product's draft submission.
#
# PRODUCT_ID and TOKEN come from the calling step's env.
set -euo pipefail

curl -sf -X POST \
  "https://api.addons.microsoftedge.microsoft.com/v1/products/${PRODUCT_ID}/submissions/draft/package" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/zip" \
  --data-binary @extension.zip
