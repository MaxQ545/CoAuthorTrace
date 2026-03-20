"""
Admin authentication utilities using JWT.
"""
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings

_bearer_scheme = HTTPBearer()


def verify_password(password: str) -> bool:
    """Check if the provided password matches the admin password using constant-time comparison."""
    if not settings.admin.password:
        return False
    return hmac.compare_digest(password, settings.admin.password)


def create_access_token() -> str:
    """Create a JWT access token for the admin."""
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.admin.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.admin.jwt_secret, algorithm="HS256")


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency that validates the admin JWT token."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.admin.jwt_secret,
            algorithms=["HS256"],
        )
        if payload.get("sub") != "admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
