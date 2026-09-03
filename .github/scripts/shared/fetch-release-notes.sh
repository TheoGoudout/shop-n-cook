#!/usr/bin/env bash
# Put the release's body into a step output, for the three publishers that
# forward it to a store listing.
#
# Read off the release rather than github.event.release.body, which is empty
# when this workflow is called rather than triggered.
#
# GH_TOKEN, TAG and REPOSITORY come from the calling step's env.
set -euo pipefail

{
  echo "body<<RELEASE_BODY_EOF"
  gh release view "$TAG" --repo "$REPOSITORY" --json body --jq .body
  echo "RELEASE_BODY_EOF"
} >> "$GITHUB_OUTPUT"
