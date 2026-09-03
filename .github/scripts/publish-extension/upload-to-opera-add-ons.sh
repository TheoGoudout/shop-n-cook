#!/usr/bin/env bash
# Upload the packaged zip to the Opera add-ons store.
#
# EMAIL, PASSWORD and EXTENSION_ID come from the calling step's env — all three
# were on this command line before, which put the store password in argv.
set -euo pipefail

ext-opera-upload \
  --email "$EMAIL" \
  --password "$PASSWORD" \
  --extension-id "$EXTENSION_ID" \
  --zip extension.zip
