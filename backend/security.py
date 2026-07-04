"""Password hashing (bcrypt) and JWT bearer authentication."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .db import require_db
from .errors import unauthorized

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRES_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise unauthorized("Token has expired. Log in again.")
    except jwt.InvalidTokenError:
        raise unauthorized("Invalid authentication token.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency: resolve the Bearer token into a user document."""
    if credentials is None or not credentials.credentials:
        raise unauthorized("Missing Authorization header (Bearer token required).")

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = ObjectId(payload.get("sub", ""))
    except (InvalidId, TypeError):
        raise unauthorized("Token subject is not a valid user id.")

    user = require_db().users.find_one({"_id": user_id})
    if user is None:
        raise unauthorized("User for this token no longer exists.")
    return user
