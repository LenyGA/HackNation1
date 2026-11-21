"""Warm the caches after a deploy (plan M8.3): run real analyses for a few reference parcels.

This fills the disk cache with tiles, scenes and the historical weather that never change, and opens
connections to every source. It does NOT store any prepared result for jury parcels: every report is
still computed by the app from the fetched data.

Standard library only, so it runs inside the production image:
    docker compose exec app python scripts/warm_cache.py
    python scripts/warm_cache.py --base https://example.pl
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date

# Reference parcels from different regions (the full set is planned in tests/e2e/parcels.yaml, M9.1).
PARCELS: list[tuple[str, str]] = [
    ("141201_1.0001.6509", "winter_wheat"),
    ("302108_5.0014.88/8", "maize"),
]
HISTORICAL_DATE = date(2024, 7, 15)
POLL_S = 1.0
TIMEOUT_S = 90.0


def _call(base: str, path: str, body: dict[str, str] | None = None) -> dict[str, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}/api{path}",
        data=data,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json", "User-Agent": "RolnikSzukaWody-warm-cache"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result: dict[str, object] = json.loads(resp.read())
        return result


def _run_one(base: str, parcel_id: str, crop_id: str, day: date) -> bool:
    t0 = time.monotonic()
    created = _call(
        base, "/analyses", {"parcel_id": parcel_id, "crop_id": crop_id, "analysis_date": day.isoformat()}
    )
    job_id = str(created["id"])
    while time.monotonic() - t0 < TIMEOUT_S:
        status = _call(base, f"/analyses/{job_id}")
        if status["status"] in ("done", "failed"):
            sources = status.get("sources")
            states = (
                ", ".join(f"{s['name']}={s['status']}" for s in sources) if isinstance(sources, list) else ""
            )
            print(f"{parcel_id} {day} {status['status']} in {time.monotonic() - t0:.1f} s  [{states}]")
            return status["status"] == "done"
        time.sleep(POLL_S)
    print(f"{parcel_id} {day} still running after {TIMEOUT_S:.0f} s")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="app address (default: %(default)s)")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    # The server's UTC date is never ahead of the Polish date, so it always passes the API's "<= today" check.
    days = [date.today(), HISTORICAL_DATE]
    ok = True
    for parcel_id, crop_id in PARCELS:
        for day in days:
            try:
                ok = _run_one(base, parcel_id, crop_id, day) and ok
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
                print(f"{parcel_id} {day} error: {exc}")
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
