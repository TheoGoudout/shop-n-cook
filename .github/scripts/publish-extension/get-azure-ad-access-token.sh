#!/usr/bin/env bash
# Exchange the Edge partner credentials for an Azure AD access token.
#
# TENANT_ID, CLIENT_ID and CLIENT_SECRET come from the calling step's env. All
# three used to be interpolated onto this curl command line, which put the
# client secret in the process's argv.
set -euo pipefail

TOKEN=$(curl -sf -X POST \
  "https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token" \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${CLIENT_SECRET}" \
  -d "scope=https://api.addons.microsoftedge.microsoft.com/.default" \
  -d "grant_type=client_credentials" \
  | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "::error::Azure AD returned no access token for the Edge partner account."
  exit 1
fi

# Masked, as the Chrome job already masked its own. Without this the token went
# into $GITHUB_OUTPUT unmasked, so any later step echoing that output — or any
# `set -x` — would print a live store credential into the run log.
echo "::add-mask::${TOKEN}"
echo "token=${TOKEN}" >> "$GITHUB_OUTPUT"
