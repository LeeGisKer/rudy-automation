from __future__ import annotations

"""Generate synthetic receipt data for testing the dashboard.

Creates JSON artifacts under `src/dashboard/uploads/` and persists them
to SQLite so reports and share links work immediately. By default it
generates ~30 batches per month across the last 6 months.

Usage examples:
  python src/dashboard/seed_data.py
  python src/dashboard/seed_data.py --months 6 --batches-per-month 40 --avg-items 3 --reset
"""

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
import calendar

# Allow importing storage alongside this module
try:
    from . import storage
except Exception:
    import sys as _sys
    _sys.path.append(str(Path(__file__).resolve().parent))
    import storage  # type: ignore


UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


JOBS = [
    "Pine Ave Renovation",
    "Elm St Roofing",
    "Main St Office",
    "Warehouse Upgrade",
    "Lakeside Cabin",
    "Maple Rd Paving",
    "Downtown Loft",
]


def rand_job() -> str:
    return random.choice(JOBS)


def rand_category() -> str | None:
    # ~30% fuel, rest None (other)
    return "fuel" if random.random() < 0.3 else None


def rand_total(category: str | None) -> float:
    if category == "fuel":
        return round(random.uniform(35.0, 140.0), 2)
    return round(random.uniform(20.0, 650.0), 2)


def month_start_end(dt: datetime) -> tuple[datetime, datetime]:
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    end = dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)
    return start, end


def gen_timestamp_within(month_dt: datetime) -> datetime:
    start, end = month_start_end(month_dt)
    span = int((end - start).total_seconds())
    offs = random.randint(0, span)
    return start + timedelta(seconds=offs)


def seed_month(
    conn,
    month_dt: datetime,
    *,
    batches: int,
    avg_items: int,
) -> int:
    """Seed one month worth of data; returns number of items created."""
    count = 0
    for _ in range(batches):
        # Batch timestamp and id (matches app's batch_id format)
        ts = gen_timestamp_within(month_dt)
        bid = ts.strftime("%Y%m%d%H%M%S") + f"_{uuid4().hex[:6]}"
        # Items per batch ~ Poisson-like around avg_items (min 1, max 5)
        n = max(1, min(5, int(random.gauss(avg_items, 1)) or 1))
        for i in range(1, n + 1):
            job = rand_job()
            cat = rand_category()
            total = rand_total(cat)
            # Simulate a camera filename
            orig = f"IMG_{ts.strftime('%Y%m%d')}_{uuid4().hex[:4]}.jpg"
            imgfile = f"{uuid4().hex}_{orig}"
            stem = uuid4().hex
            payload = {
                "file": imgfile,
                "original_name": orig,
                "batch_id": bid,
                "batch_seq": i,
                "batch_total": n,
                "job_name": job,
                "total": total,
            }
            if cat:
                payload["category"] = cat

            json_path = UPLOAD_DIR / f"{stem}.json"
            json_path.write_text(json.dumps(payload, indent=2))
            # Persist via storage helper using existing connection
            storage.save_from_json_path(json_path, conn=conn)
            # Stamp created_at/updated_at to the batch timestamp for realistic reports
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE tickets SET created_at=?, updated_at=? WHERE id=?;",
                (ts_str, ts_str, stem),
            )
            count += 1
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the dashboard with synthetic data")
    ap.add_argument("--months", type=int, default=6, help="How many months back (default 6)")
    ap.add_argument("--batches-per-month", type=int, default=30, help="Batches per month (default 30)")
    ap.add_argument("--avg-items", type=int, default=2, help="Average items per batch (default 2)")
    ap.add_argument("--reset", action="store_true", help="Clear existing JSONs and tickets before seeding")
    args = ap.parse_args()

    # Optionally reset uploads and DB
    if args.reset:
        for f in UPLOAD_DIR.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass
        conn = storage._connect()  # type: ignore[attr-defined]
        try:
            storage._init(conn)  # type: ignore[attr-defined]
            conn.execute("DELETE FROM tickets;")
            conn.commit()
            try:
                conn.execute("VACUUM;")
            except Exception:
                pass
        finally:
            conn.close()

    conn = storage._connect()  # type: ignore[attr-defined]
    total_items = 0
    try:
        storage._init(conn)  # type: ignore[attr-defined]
        now = datetime.utcnow().replace(day=15, hour=12, minute=0, second=0, microsecond=0)
        for m in range(args.months):
            # Month m months ago
            year = (now.year if now.month - m > 0 else now.year - 1)
            month = ((now.month - m - 1) % 12) + 1
            month_dt = now.replace(year=year, month=month)
            created = seed_month(
                conn,
                month_dt,
                batches=args.batches_per_month,
                avg_items=args.avg_items,
            )
            total_items += created
        conn.commit()
    finally:
        conn.close()

    # Create a share link valid for 7 days for quick viewing
    token = storage.create_share(ttl_minutes=7 * 24 * 60)
    print(f"Seeded items: {total_items}")
    print(f"Uploads dir: {UPLOAD_DIR}")
    print(f"DB path: {storage.DB_PATH}")
    print(f"Sample share URL path: /share/{token}")


if __name__ == "main__":  # pragma: no cover
    # Typo-guard; correct __main__ below
    main()


if __name__ == "__main__":  # pragma: no cover
    main()
