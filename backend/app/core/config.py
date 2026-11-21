"""Application configuration. No secrets are required; every value can be overridden with RSW_* env vars."""

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_TITLE = "RolnikSzukaWody"
APP_VERSION = "0.1.0"
TEAM_NAME = "GeoSatel"

# Identifies the app to public data providers. Deliberately contains no personal data.
USER_AGENT = f"{APP_TITLE}/{APP_VERSION} (HackNation 2026 prototype)"

# Calendar dates ("today", analysis_date) are Polish local dates, independent of the server timezone.
LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Length of the historical window, counted back from analysis_date.
HISTORY_YEARS = 10


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RSW_", env_file=".env", extra="ignore")

    cache_dir: Path = Path(".cache")
    db_path: Path = Path(".cache/reports.sqlite3")
    cors_origins: list[str] = ["http://localhost:5173"]
    frontend_dist: Path = Path("../frontend/dist")
    # Default per-source timeout in seconds; sources may use a stricter one.
    source_timeout_s: float = 12.0
    # GUGiK NMT WCS was too slow from the event network (> 30 s); enable only after re-checking from the VPS.
    dem_try_nmt: bool = False


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


@lru_cache
def get_settings() -> Settings:
    return Settings()
