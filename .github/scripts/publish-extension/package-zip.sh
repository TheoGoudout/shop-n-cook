#!/usr/bin/env bash
# Zip the built extension into the artifact every publisher downloads.
set -euo pipefail

cd extension/dist
zip -r ../../extension.zip .
