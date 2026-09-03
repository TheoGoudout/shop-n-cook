#!/usr/bin/env bash
# Install the AMO signing tool.
#
# Pinned to a major line. Unpinned, `bun add -g web-ext` resolved whatever was
# newest that morning, so the tool that signs and submits the add-on could
# change under a release without anything in the diff saying so.
set -euo pipefail

bun add -g "web-ext@^8"
