"""Saved reports in SQLite under a random, unguessable id (plan step M6.1).

The stored JSON contains only the parcel, the crop, the date and computed results — no IP address or any other
personal data (CLAUDE.md rule 10).
"""

import asyncio
import re
import secrets
import sqlite3
from pathlib import Path

from app.core.config import APP_TITLE, get_settings
from app.report.models import Report

# 16 random bytes → 22 url-safe characters (128 bits): not guessable, not enumerable.
REPORT_ID_BYTES = 16
REPORT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    body TEXT NOT NULL
)
"""


def new_report_id() -> str:
    return secrets.token_urlsafe(REPORT_ID_BYTES)


def valid_report_id(report_id: str) -> bool:
    return bool(REPORT_ID_RE.match(report_id))


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute(_SCHEMA)
    return conn


def _save(path: Path, report: Report) -> None:
    conn = _connect(path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO reports (id, created_at, body) VALUES (?, ?, ?)",
                (report.id, report.created_at.isoformat(), report.model_dump_json()),
            )
    finally:
        conn.close()


OLD_APP_NAME = "RolnikSzukaWody"


def _load(path: Path, report_id: str) -> Report | None:
    if not path.exists():
        return None
    conn = _connect(path)
    try:
        row = conn.execute("SELECT body FROM reports WHERE id = ?", (report_id,)).fetchone()
    finally:
        conn.close()
    # Reports saved before 22.11.2026 carry the former test name of the app in their stored texts.
    return Report.model_validate_json(row[0].replace(OLD_APP_NAME, APP_TITLE)) if row else None


async def save_report(report: Report, db_path: Path | None = None) -> None:
    await asyncio.to_thread(_save, db_path or get_settings().db_path, report)


async def load_report(report_id: str, db_path: Path | None = None) -> Report | None:
    if not valid_report_id(report_id):
        return None
    return await asyncio.to_thread(_load, db_path or get_settings().db_path, report_id)
