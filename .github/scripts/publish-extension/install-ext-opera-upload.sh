#!/usr/bin/env bash
# Install the Opera uploader.
#
# Opera has no official REST API; this drives the partner site with Puppeteer.
# Pinned to a major line for the same reason web-ext is: unpinned, the tool
# holding the store password changed whenever its author published.
#
# `bun add -g` rather than `npm install -g`: this was the only npm invocation in
# an otherwise all-bun repository, so it pulled a second package manager onto
# the runner to install one CLI.
set -euo pipefail

bun add -g "ext-opera-upload@^1"
