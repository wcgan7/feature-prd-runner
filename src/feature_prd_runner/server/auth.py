"""Simple authentication for the web dashboard."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    """User model."""

    username: str
    disabled: bool = False


class AuthConfig:
    """Authentication configuration."""

    def __init__(self):
        """Initialize auth config from environment."""
        # Auth is disabled by default for local development
        self.enabled = os.getenv("DASHBOARD_AUTH_ENABLED", "false").lower() == "true"

        # Simple username/password (can be overridden via env)
        self.username = os.getenv("DASHBOARD_USERNAME", "admin")
        self.password = os.getenv("DASHBOARD_PASSWORD", "admin")

        # JWT secret (auto-generated if not provided)
        self.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "dev-secret-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("DASHBOARD_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours


# Global config instance
auth_config = AuthConfig()


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password.

    Args:
        username: Username to verify.
        password: Password to verify.

    Returns:
        True if credentials are valid.
    """
    if not auth_config.enabled:
        return True  # Auth disabled, always succeed

    return username == auth_config.username and password == auth_config.password


def get_user(username: str) -> Optional[User]:
    """Get user by username.

    Args:
        username: Username to look up.

    Returns:
        User object or None.
    """
    if username == auth_config.username:
        return User(username=username)
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token.

    Args:
        data: Data to encode in token.
        expires_delta: Optional expiration time delta.

    Returns:
        Encoded JWT token.
    """
    try:
        import jwt
    except ImportError:
        # JWT not available, return a simple token
        return f"simple-token-{data.get('sub', 'unknown')}"

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=auth_config.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, auth_config.secret_key, algorithm=auth_config.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[str]:
    """Decode and verify JWT access token.

    Args:
        token: JWT token to decode.

    Returns:
        Username from token or None if invalid.
    """
    if not auth_config.enabled:
        return auth_config.username  # Auth disabled, return default user

    try:
        import jwt
    except ImportError:
        # JWT not available, use simple token validation
        if token.startswith("simple-token-"):
            return token.replace("simple-token-", "")
        return None

    try:
        payload = jwt.decode(token, auth_config.secret_key, algorithms=[auth_config.algorithm])
        username: str = payload.get("sub")
        return username
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
