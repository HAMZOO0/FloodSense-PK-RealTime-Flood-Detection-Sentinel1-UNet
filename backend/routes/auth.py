"""User accounts for the mobile/web apps (register, login, profile)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pymongo.errors import DuplicateKeyError

from ..db import require_db
from ..errors import conflict, unauthorized
from ..schemas import (
    AuthResponse,
    DistrictUpdateRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from ..security import create_access_token, get_current_user, hash_password, verify_password
from ..services import geodata

router = APIRouter(prefix="/auth", tags=["Auth"])


def _user_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        username=user["username"],
        district=user.get("district"),
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest):
    """Create an account and return a JWT immediately (auto-login)."""
    db = require_db()

    district = None
    if body.district:
        # Normalise to the canonical shapefile name (raises 404 if unknown).
        district, _, _ = geodata.find_district(body.district)

    user = {
        "username": body.username.strip().lower(),
        "password_hash": hash_password(body.password),
        "district": district,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = db.users.insert_one(user)
    except DuplicateKeyError:
        raise conflict(
            "USERNAME_TAKEN", f"Username '{body.username}' is already registered."
        )

    user["_id"] = result.inserted_id
    token = create_access_token(str(result.inserted_id), user["username"])
    return AuthResponse(token=token, user=_user_out(user))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    """Exchange username + password for a JWT bearer token."""
    db = require_db()
    user = db.users.find_one({"username": body.username.strip().lower()})
    if user is None or not verify_password(body.password, user.get("password_hash", "")):
        raise unauthorized("Invalid username or password.")

    token = create_access_token(str(user["_id"]), user["username"])
    return AuthResponse(token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    """Profile of the authenticated user."""
    return _user_out(user)


@router.put("/me/district", response_model=UserOut)
def update_district(body: DistrictUpdateRequest, user: dict = Depends(get_current_user)):
    """Change the user's home district (used for personalised alerts)."""
    district, _, _ = geodata.find_district(body.district)
    db = require_db()
    db.users.update_one({"_id": user["_id"]}, {"$set": {"district": district}})
    user["district"] = district
    return _user_out(user)
