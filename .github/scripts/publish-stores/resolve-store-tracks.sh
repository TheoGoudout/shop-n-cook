#!/usr/bin/env bash
# Map "is this a pre-release?" onto each store's staging channel.
#
# PRERELEASE comes from the calling step's env.
set -euo pipefail

if [ "$PRERELEASE" = "true" ]; then
  ANDROID_TRACK=internal
  IOS_LANE=beta
  WINDOWS_BETA=true
else
  # `alpha`, not `production`: the Play upload below also uses `status: draft`,
  # so promotion to production is a deliberate click in the Play Console rather
  # than a side effect of publishing a GitHub release.
  ANDROID_TRACK=alpha
  IOS_LANE=release
  WINDOWS_BETA=false
fi

{
  echo "android_track=$ANDROID_TRACK"
  echo "ios_lane=$IOS_LANE"
  echo "windows_beta=$WINDOWS_BETA"
} >> "$GITHUB_OUTPUT"
