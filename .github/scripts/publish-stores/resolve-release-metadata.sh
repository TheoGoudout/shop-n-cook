#!/usr/bin/env bash
# Read the release's display name, for the Play Console release title.
#
# GH_TOKEN, TAG and REPOSITORY come from the calling step's env.
set -euo pipefail

NAME=$(gh release view "$TAG" --repo "$REPOSITORY" --json name --jq '.name // ""')
echo "name=${NAME:-$TAG}" >> "$GITHUB_OUTPUT"
