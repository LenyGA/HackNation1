"""Saved reports in SQLite (plan M6.1): round-trip, unguessable ids, invalid ids."""

import asyncio
from pathlib import Path

from app.report.storage import load_report, new_report_id, save_report, valid_report_id
from tests.report.builders import rich_report


def test_ids_are_22_chars_and_unique() -> None:
    ids = {new_report_id() for _ in range(2000)}
    assert len(ids) == 2000
    assert all(len(i) == 22 and valid_report_id(i) for i in ids)


def test_save_load_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "sub" / "reports.sqlite3"
    r = rich_report()
    asyncio.run(save_report(r, db))
    loaded = asyncio.run(load_report(r.id, db))
    assert loaded is not None
    assert loaded.model_dump_json() == r.model_dump_json()


def test_unknown_and_invalid_ids(tmp_path: Path) -> None:
    db = tmp_path / "reports.sqlite3"
    assert asyncio.run(load_report(new_report_id(), db)) is None  # db does not exist yet
    asyncio.run(save_report(rich_report(), db))
    assert asyncio.run(load_report(new_report_id(), db)) is None
    for bad in ("", "short", "x" * 23, "../../etc/passwd_xxxxx", "' OR 1=1 --xxxxxxxxxxx", "a" * 21 + "!"):
        assert not valid_report_id(bad)
        assert asyncio.run(load_report(bad, db)) is None


def test_stored_body_has_no_personal_data(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "reports.sqlite3"
    r = rich_report()
    asyncio.run(save_report(r, db))
    cols = [row[1] for row in sqlite3.connect(db).execute("PRAGMA table_info(reports)")]
    assert cols == ["id", "created_at", "body"]
