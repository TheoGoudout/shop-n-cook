#!/usr/bin/env bash
# Put the release's body into a step output, for the three publishers that
# forward it to a store listing.
#
# Read off the release rather than github.event.release.body, which is empty
# when this workflow is called rather than triggered.
#
# GH_TOKEN, TAG and REPOSITORY come from the calling step's env.
set -euo pipefail

# Each entry scripts/release_notes.py writes ends in its pull request and
# author as Markdown links. They belong on GitHub, but a store listing shows
# them as raw text and Google Play counts them against its 500 characters, so
# they are cut here, leaving `* Title.`.
{
  echo "body<<RELEASE_BODY_EOF"
  gh release view "$TAG" --repo "$REPOSITORY" --json body --jq .body \
    | sed -E 's/ PR \[#[0-9]+\]\([^)]*\) by .*$//'
  echo "RELEASE_BODY_EOF"
} >> "$GITHUB_OUTPUT"
