"""Pydantic request/response models for the REST API."""

from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    district: Optional[str] = Field(
        None, description="Home district used for personalised alerts."
    )


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: str
    username: str
    district: Optional[str] = None


class AuthResponse(BaseModel):
    success: bool = True
    token: str
    token_type: str = "bearer"
    user: UserOut


class DistrictUpdateRequest(BaseModel):
    district: str = Field(..., min_length=2, max_length=100)


# ── Analysis / pipeline ─────────────────────────────────────────────────────
class AnalysisJobResponse(BaseModel):
    success: bool = True
    job_id: str
    status: str
    district: str
    message: str


class PipelineRequest(BaseModel):
    population_at_risk: Optional[int] = Field(
        None,
        ge=0,
        description="Override the population estimate (default: affected km² × 350).",
    )


# ── Alerts ──────────────────────────────────────────────────────────────────
class AlertCreateRequest(BaseModel):
    district: str = Field(..., min_length=2, max_length=100)
    severity: str = Field(
        "MODERATE", pattern="^(LOW|MODERATE|HIGH)$", description="LOW | MODERATE | HIGH"
    )
    message: str = Field(..., min_length=5, max_length=2000)


# ── Chat ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(3, ge=1, le=10, description="Number of knowledge chunks to retrieve.")
