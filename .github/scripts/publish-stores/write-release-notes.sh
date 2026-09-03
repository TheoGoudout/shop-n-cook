#!/usr/bin/env bash
# Put the release body where upload-google-play's whatsNewDirectory expects it.
#
# GH_TOKEN, TAG and REPOSITORY come from the calling step's env.
set -euo pipefail

mkdir -p whats-new
# Read from the release rather than github.event.release.body, which is empty
# when this workflow is called rather than triggered directly.
gh release view "$TAG" --repo "$REPOSITORY" --json body --jq .body > whats-new/whatsnew-en-US
