#!/usr/bin/env bash
# Unpack the built zip into the source directory web-ext signs from.
set -euo pipefail

mkdir ext-src
cd ext-src
unzip ../extension.zip
