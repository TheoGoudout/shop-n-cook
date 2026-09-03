"""Mint a Chrome Web Store access token from the service-account credentials.

Invoked by publish-extension/get-access-token-from-service-account.sh. Lives
here rather than as a `python3 -c "..."` heredoc inside that script so ruff can
see it: a syntax error in the heredoc form was only ever discoverable by cutting
a release.

Reads SA_JSON from the environment and prints the token on stdout. The caller
masks it before it reaches a step output.
"""

import json
import os

import google.auth.transport.requests as req
import google.oauth2.service_account as sa

SCOPES = ["https://www.googleapis.com/auth/chromewebstore"]


def main() -> None:
    creds = sa.Credentials.from_service_account_info(
        json.loads(os.environ["SA_JSON"]), scopes=SCOPES
    )
    creds.refresh(req.Request())
    print(creds.token)


if __name__ == "__main__":
    main()
