#!/usr/bin/env bash
# Export the archive into an uploadable package.
set -euo pipefail

xcodebuild -exportArchive \
  -archivePath build/ShopNCook.xcarchive \
  -exportPath build/export \
  -exportOptionsPlist ExportOptions.plist
