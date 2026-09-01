import jwt
from jwt.exceptions import InvalidTokenError
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core import security
from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)


def user_or_ip_key(request: Request) -> str:
    """Rate-limit key: the authenticated user when identifiable, else the client IP.

    The default IP key is a poor fit for login-only routes — everyone behind a
    single NAT or carrier CGNAT would share one bucket. slowapi calls this before
    FastAPI's dependency results are reachable, so the bearer token is decoded
    here rather than read off the resolved ``CurrentUser``.
    """
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        try:
            payload = jwt.decode(
                authorization[len("Bearer ") :],
                settings.SECRET_KEY,
                algorithms=[security.ALGORITHM],
            )
        except InvalidTokenError:
            pass
        else:
            subject = payload.get("sub")
            if subject:
                return f"user:{subject}"
    return get_remote_address(request)
