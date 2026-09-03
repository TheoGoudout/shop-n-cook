#!/usr/bin/env bash
# Cut the notes for this version, into the file the draft release is created from.
#
# VERSION and BODY_FILE come from the calling step's env.
set -euo pipefail

# --insert updates release-notes.md; stdout is the body for the release.
bun scripts/release-notes.mjs --version "$VERSION" --insert > "$BODY_FILE"
echo "--- generated notes ---"
cat "$BODY_FILE"
