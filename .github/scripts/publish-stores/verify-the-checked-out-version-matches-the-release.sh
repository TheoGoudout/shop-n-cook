#!/usr/bin/env bash
# Refuse to build if the tree is not at the version being released.
#
# scripts/set-version.mjs commits versionName and versionCode, so a mismatch
# here means the tag was cut from a commit the bump never reached.
#
# VERSION comes from the calling step's env.
set -euo pipefail
cd mobile/android/app

ACTUAL=$(grep -oP '(?<=versionName ")[^"]*' build.gradle)
if [ "$ACTUAL" != "$VERSION" ]; then
  echo "::error::build.gradle says versionName ${ACTUAL} but the release is ${VERSION}."
  exit 1
fi

echo "build.gradle is at ${ACTUAL} (versionCode $(grep -oP '(?<=versionCode )\d+' build.gradle))."
