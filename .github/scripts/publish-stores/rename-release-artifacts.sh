#!/usr/bin/env bash
# Give the Android outputs the release's own name.
#
# VERSION comes from the calling step's env.
set -euo pipefail

cp mobile/android/app/build/outputs/bundle/release/app-release.aab "shop-n-cook-${VERSION}.aab"
cp mobile/android/app/build/outputs/apk/release/app-release.apk "shop-n-cook-${VERSION}.apk"
