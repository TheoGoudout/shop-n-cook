"""Sign a short-lived HS256 JWT for the addons.mozilla.org API.

Invoked by publish-extension/set-release-notes-on-amo.sh. AMO's v5 API wants a
JWT whose issuer is the API key and whose lifetime is at most five minutes;
hand-rolling it here avoids adding a PyJWT install to a job that needs nothing
else from Python.

Reads API_KEY and API_SECRET from the environment and prints the token.
"""

import base64
import hashlib
import hmac
import json
import os
import time

# A minute is ample: the token is minted immediately before the one request
# that uses it.
LIFETIME_SECONDS = 60


def b64url(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    now = int(time.time())
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}))
    payload = b64url(
        json.dumps(
            {"iss": os.environ["API_KEY"], "iat": now, "exp": now + LIFETIME_SECONDS}
        )
    )
    message = f"{header}.{payload}"
    signature = b64url(
        hmac.new(
            os.environ["API_SECRET"].encode(), message.encode(), hashlib.sha256
        ).digest()
    )
    print(f"{message}.{signature}")


if __name__ == "__main__":
    main()
