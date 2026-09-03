#!/usr/bin/env bash
# Promote the Edge draft submission for review.
#
# PRODUCT_ID and TOKEN come from the calling step's env.
set -euo pipefail

curl -sf -X POST \
  "https://api.addons.microsoftedge.microsoft.com/v1/products/${PRODUCT_ID}/submissions" \
  -H "Authorization: Bearer ${TOKEN}"
