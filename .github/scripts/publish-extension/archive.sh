#!/usr/bin/env bash
# Build the signed archive.
#
# TEAM_ID comes from the calling step's env; it was interpolated into the
# xcodebuild command line before.
set -euo pipefail

xcodebuild archive \
  -project ShopNCook/ShopNCook.xcodeproj \
  -scheme ShopNCook \
  -archivePath build/ShopNCook.xcarchive \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$TEAM_ID"
