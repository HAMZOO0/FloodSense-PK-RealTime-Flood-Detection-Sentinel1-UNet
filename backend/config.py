"""Central configuration loaded from environment / .env."""

import os

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(key: str, default: str = "") -> str:
    """Read an env var tolerating stray whitespace in keys/values (.env quirks)."""
    value = os.getenv(key) or os.getenv(f" {key}") or default
    return value.strip() if isinstance(value, str) else value


class Settings:
    # MongoDB
    MONGO_URI: str = _env("MONGO_URI")
    MONGO_DB_NAME: str = _env("MONGO_DB_NAME", "floodsense")

    # Auth
    JWT_SECRET: str = _env("JWT_SECRET", "floodsense-dev-secret-change-me-now")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_HOURS: int = int(_env("JWT_EXPIRES_HOURS", "168"))  # 7 days

    # Google Earth Engine
    PROJECT_ID: str = _env("PROJECT_ID")
    GEE_CLIENT_EMAIL: str = _env("GEE_CLIENT_EMAIL")
    GEE_PRIVATE_KEY: str = _env("GEE_PRIVATE_KEY")

    # Data
    SHAPEFILE: str = os.path.join(ROOT_DIR, "pakistan_districts.json")

    # Analysis defaults
    SAR_IMAGE_SIZE: int = int(_env("SAR_IMAGE_SIZE", "512"))
    SAR_LOOKBACK_DAYS: int = int(_env("SAR_LOOKBACK_DAYS", "30"))
    RIVER_CACHE_MINUTES: int = int(_env("RIVER_CACHE_MINUTES", "30"))
    ESTIMATED_POP_DENSITY_PER_KM2: int = 350

    # Alerts are auto-created for analyses at or above this risk score (1-10).
    ALERT_RISK_THRESHOLD: float = 4.0


settings = Settings()
