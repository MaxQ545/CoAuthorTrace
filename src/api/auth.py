"""
Admin authentication utilities using JWT with role-based access control.
"""
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings

_bearer_scheme = HTTPBearer()


def _get_admin_users() -> dict:
    """Build the admin users dict from settings."""
    users = {
        "admin": {"password": settings.admin.password, "role": "admin"},
    }
    if settings.admin.viewer_password:
        users["viewer"] = {"password": settings.admin.viewer_password, "role": "viewer"}
    return users


def verify_password(password: str, username: Optional[str] = None) -> Optional[dict]:
    """Check credentials and return user info dict or None.

    For backward compatibility, if username is None, try matching against
    the admin password first, then viewer password.
    """
    users = _get_admin_users()

    if username:
        user = users.get(username)
        if user and hmac.compare_digest(password, user["password"]):
            return {"username": username, "role": user["role"]}
        return None

    for uname, user in users.items():
        if user["password"] and hmac.compare_digest(password, user["password"]):
            return {"username": uname, "role": user["role"]}
    return None


def create_access_token(username: str = "admin", role: str = "admin") -> str:
    """Create a JWT access token for the given user."""
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.admin.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.admin.jwt_secret, algorithm="HS256")


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.admin.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sub = payload.get("sub")
    if sub not in ("admin", "viewer"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency that validates any admin/viewer JWT token."""
    payload = _decode_token(credentials.credentials)
    return payload["sub"]


def require_role(required_role: str):
    """Return a FastAPI dependency that checks the user has the required role."""

    def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    ) -> dict:
        payload = _decode_token(credentials.credentials)
        role = payload.get("role", "admin")
        if required_role == "admin" and role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions — admin role required",
            )
        return payload

    return dependency
