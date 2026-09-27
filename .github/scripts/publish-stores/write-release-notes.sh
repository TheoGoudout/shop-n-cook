#!/usr/bin/env bash
# Put the release body where upload-google-play's whatsNewDirectory expects it.
#
# Google Play rejects release notes over 500 characters, and the release body
# of anything bigger than a patch is longer than that (v1.6.0's was 1,475). So
# the notes are cut at the last whole line that fits, with a pointer to the
# full notes. The body itself is untouched: the other stores and GitHub still
# show all of it.
#
# GH_TOKEN, TAG and REPOSITORY come from the calling step's env.
set -euo pipefail

mkdir -p whats-new
# Read from the release rather than github.event.release.body, which is empty
# when this workflow is called rather than triggered directly.
gh release view "$TAG" --repo "$REPOSITORY" --json body --jq .body \
  | python3 "$(dirname "$0")/../lib/fit_release_notes.py" 500 \
  > whats-new/whatsnew-en-US
