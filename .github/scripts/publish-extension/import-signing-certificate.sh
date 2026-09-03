#!/usr/bin/env bash
# Load the Apple distribution certificate into a keychain codesign can reach.
#
# CERTIFICATE and CERTIFICATE_PASSWORD come from the calling step's env.
set -euo pipefail

# A run-scoped keychain with a generated password, matching publish-stores.yml's
# iOS job. This job used to create `build.keychain` with an empty password and
# make it the default — which leaves an unlocked, password-less keychain holding
# a distribution certificate as the default for everything that follows.
KEYCHAIN="$RUNNER_TEMP/tmp-${GITHUB_RUN_ID}.keychain-db"
KEYCHAIN_PASSWORD=$(openssl rand -base64 24)
echo "::add-mask::${KEYCHAIN_PASSWORD}"

echo "$CERTIFICATE" | base64 --decode > "$RUNNER_TEMP/cert.p12"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security import "$RUNNER_TEMP/cert.p12" -k "$KEYCHAIN" -P "$CERTIFICATE_PASSWORD" \
  -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

# Prepended to the search list rather than replacing it, so the system keychain
# (and the Apple intermediate certificates in it) stays reachable.
security list-keychains -d user -s "$KEYCHAIN" "$(security list-keychains -d user | tr -d '\n" ')"

rm -f "$RUNNER_TEMP/cert.p12"
