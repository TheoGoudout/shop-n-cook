#!/usr/bin/env bash
# Load the Apple distribution certificate into a run-scoped keychain.
#
# CERT_BASE64 and CERT_PASSWORD come from the calling step's env.
set -euo pipefail

# Generated rather than derived from github.run_id, which is not a secret and is
# printed on every run page — so the keychain holding a distribution certificate
# was protected by a password anyone could read off the URL.
KEYCHAIN="$RUNNER_TEMP/build.keychain"
KEYCHAIN_PASSWORD=$(openssl rand -base64 24)
echo "::add-mask::${KEYCHAIN_PASSWORD}"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

printf '%s' "$CERT_BASE64" | base64 -d > "$RUNNER_TEMP/cert.p12"
security import "$RUNNER_TEMP/cert.p12" \
  -P "$CERT_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN"
security set-key-partition-list \
  -S apple-tool:,apple: -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

# Prepended to the search list, so the system keychain and its Apple
# intermediates stay reachable.
security list-keychains -d user -s "$KEYCHAIN" \
  "$(security list-keychains -d user | head -1 | tr -d '"')"

rm -f "$RUNNER_TEMP/cert.p12"
