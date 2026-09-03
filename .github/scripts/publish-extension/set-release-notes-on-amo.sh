#!/usr/bin/env bash
# Publish the release notes as the add-on version's changelog on AMO.
#
# ADDON_SLUG, API_KEY, API_SECRET, VERSION and RELEASE_BODY come from the
# calling step's env; the JWT helper reads the two credentials itself.
set -euo pipefail

JWT=$(python3 .github/scripts/lib/amo_jwt.py)
echo "::add-mask::${JWT}"

# json.dumps rather than string interpolation: the release body is Markdown with
# quotes, backslashes and newlines in it, any of which would otherwise produce
# an invalid request body.
NOTES_JSON=$(python3 -c 'import json, os; print(json.dumps(os.environ["RELEASE_BODY"]))')

curl -sf -X PATCH \
  "https://addons.mozilla.org/api/v5/addons/addon/${ADDON_SLUG}/versions/${VERSION}/" \
  -H "Authorization: JWT ${JWT}" \
  -H "Content-Type: application/json" \
  -d "{\"release_notes\":{\"en-US\":${NOTES_JSON}}}"
