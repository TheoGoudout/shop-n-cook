#!/usr/bin/env bash
# Exchange the Chrome service-account credentials for an access token.
#
# SA_JSON comes from the calling step's env, and is read by the Python helper
# rather than passed as an argument.
set -euo pipefail

# Pinned. This is the one dependency in the workflow that is not SHA-pinned by
# being an action, and `pip install google-auth requests` resolved whatever was
# newest on PyPI at release time — so the code that mints a store credential was
# a function of the date.
pip install --quiet "google-auth>=2.38,<3" "requests>=2.32,<3"

TOKEN=$(python3 .github/scripts/lib/chrome_token.py)

# Masked before it reaches $GITHUB_OUTPUT, so it cannot be echoed by a later
# step or land in the run log.
echo "::add-mask::${TOKEN}"
echo "token=${TOKEN}" >> "$GITHUB_OUTPUT"
