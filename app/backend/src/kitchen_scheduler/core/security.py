from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from kitchen_scheduler.core.config import get_settings

settings = get_settings()


def create_access_token(*, subject: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload: Dict[str, Any] = {"sub": subject, "iat": now.timestamp(), "exp": expire.timestamp()}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def verify_demo_user(username: str, password: str) -> Optional[dict[str, str]]:
    """
    Placeholder user verification used until the persistence layer is wired.

    In development the default credentials are planner / planner.
    """
    demo_user = {"username": "planner", "password": "planner", "role": "Planner"}
    if username == demo_user["username"] and password == demo_user["password"]:
        return demo_user
    return None
