#!/usr/bin/env bash
# Put the provisioning profile where xcodebuild looks for it.
#
# PROVISIONING_PROFILE comes from the calling step's env.
set -euo pipefail

PROFILES=~/Library/MobileDevice/Provisioning\ Profiles
mkdir -p "$PROFILES"
echo "$PROVISIONING_PROFILE" | base64 --decode > "$PROFILES/profile.mobileprovision"
