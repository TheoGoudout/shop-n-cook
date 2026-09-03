#!/usr/bin/env bash
# Re-key the keystore into the format bundletool can actually read.
#
# bundletool ships its own Bouncy Castle, which chokes on newer AES-256 PKCS12
# files; the legacy 3DES format is readable by every BC version.
#
# STORE_PASS comes from the calling step's env.
set -euo pipefail
cd mobile/android

keytool -importkeystore \
  -srckeystore android.keystore \
  -srcstoretype PKCS12 \
  -srcstorepass "$STORE_PASS" \
  -destkeystore android-legacy.keystore \
  -deststoretype PKCS12 \
  -deststorepass "$STORE_PASS" \
  -noprompt \
  -J-Dkeystore.pkcs12.legacy

mv android-legacy.keystore android.keystore
