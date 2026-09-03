#!/usr/bin/env bash
# Send the exported package to App Store Connect.
#
# Every build lands in TestFlight first; App Store review has to be submitted by
# hand from App Store Connect, as there is no API to trigger it.
#
# API_KEY_ID and API_ISSUER_ID come from the calling step's env.
set -euo pipefail

PKG=$(find build/export -name '*.pkg' -print -quit)
if [ -z "$PKG" ]; then
  echo "::error::xcodebuild -exportArchive produced no .pkg to upload."
  exit 1
fi

xcrun altool --upload-app \
  --type macos \
  --file "$PKG" \
  --apiKey "$API_KEY_ID" \
  --apiIssuer "$API_ISSUER_ID"
