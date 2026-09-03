#!/usr/bin/env bash
# Build the signed Android App Bundle for the Play Store.
#
# STORE_PASSWORD, KEY_ALIAS and KEY_PASSWORD come from the calling step's env.
# All three used to be interpolated into `-P` arguments, which put two signing
# passwords into the gradle process's argv — visible to anything else on the
# runner for the length of the build.
set -euo pipefail
cd mobile/android

chmod +x gradlew
./gradlew bundleRelease \
  -Pandroid.injected.signing.store.file="$(pwd)/android.keystore" \
  -Pandroid.injected.signing.store.type=PKCS12 \
  -Pandroid.injected.signing.store.password="$STORE_PASSWORD" \
  -Pandroid.injected.signing.key.alias="$KEY_ALIAS" \
  -Pandroid.injected.signing.key.password="$KEY_PASSWORD"
