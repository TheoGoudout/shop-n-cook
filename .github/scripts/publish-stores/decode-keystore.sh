#!/usr/bin/env bash
# Write the Android signing keystore out of its base64 secret.
#
# KEYSTORE_BASE64 comes from the calling step's env — it was interpolated into
# this command line before, which put the whole keystore in the process's argv.
set -euo pipefail

printf '%s' "$KEYSTORE_BASE64" | tr -d '[:space:]' | base64 -d > mobile/android/android.keystore
