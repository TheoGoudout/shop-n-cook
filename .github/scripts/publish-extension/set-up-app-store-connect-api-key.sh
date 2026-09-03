#!/usr/bin/env bash
# Write the App Store Connect API key where altool expects to find it.
#
# API_KEY_CONTENT and API_KEY_ID come from the calling step's env. The key id
# was interpolated into the *filename* before — a secret in a path, which any
# directory listing in a later step would print.
set -euo pipefail

KEYS=~/.appstoreconnect/private_keys
mkdir -p "$KEYS"
echo "$API_KEY_CONTENT" | base64 --decode > "${KEYS}/AuthKey_${API_KEY_ID}.p8"
chmod 600 "${KEYS}/AuthKey_${API_KEY_ID}.p8"
