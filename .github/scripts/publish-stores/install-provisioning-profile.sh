#!/usr/bin/env bash
# Put the provisioning profile where xcodebuild looks for it.
#
# PROVISIONING_PROFILE_BASE64 comes from the calling step's env; it was
# interpolated into this command line before.
set -euo pipefail

PROFILES=~/Library/MobileDevice/Provisioning\ Profiles
mkdir -p "$PROFILES"
printf '%s' "$PROVISIONING_PROFILE_BASE64" | base64 -d > "$PROFILES/profile.mobileprovision"
