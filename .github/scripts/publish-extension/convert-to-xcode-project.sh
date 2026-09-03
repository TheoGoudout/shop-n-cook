#!/usr/bin/env bash
# Turn the unpacked web extension into a Safari app extension Xcode project.
set -euo pipefail

xcrun safari-web-extension-converter ext-src \
  --app-name "ShopNCook" \
  --bundle-identifier com.shopncook.extension \
  --swift \
  --no-open
