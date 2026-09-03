#!/usr/bin/env bash
# Submit the uploaded package for publication.
#
# EXTENSION_ID and TOKEN come from the calling step's env.
set -euo pipefail

RESULT=$(curl -s -X POST \
  "https://www.googleapis.com/chromewebstore/v1.1/items/${EXTENSION_ID}/publish" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"target":"default"}')

STATUS=$(echo "$RESULT" | jq -r '.status[0] // ""')
ERROR=$(echo "$RESULT" | jq -r '.error.message // ""')

# ITEM_PENDING_REVIEW = submitted for review, which is normal for an extension
# asking for broad permissions.
# "in review" error = a previous submission is still under review, so this
# package was accepted as a draft rather than rejected.
if [ "$STATUS" = "OK" ] || [ "$STATUS" = "ITEM_PENDING_REVIEW" ] \
  || echo "$ERROR" | grep -qi "in review"; then
  echo "Submitted: ${STATUS} ${ERROR}"
else
  echo "::error::Chrome Web Store publish failed: ${RESULT}"
  exit 1
fi
