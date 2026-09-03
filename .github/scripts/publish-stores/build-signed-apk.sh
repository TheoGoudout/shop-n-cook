#!/usr/bin/env bash
# Build the signed APK attached to the GitHub release for sideloading.
#
# STORE_PASSWORD, KEY_ALIAS and KEY_PASSWORD come from the calling step's env.
set -euo pipefail
cd mobile/android

./gradlew assembleRelease \
  -Pandroid.injected.signing.store.file="$(pwd)/android.keystore" \
  -Pandroid.injected.signing.store.type=PKCS12 \
  -Pandroid.injected.signing.store.password="$STORE_PASSWORD" \
  -Pandroid.injected.signing.key.alias="$KEY_ALIAS" \
  -Pandroid.injected.signing.key.password="$KEY_PASSWORD"
