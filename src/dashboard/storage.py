from __future__ import annotations

import sqlite3
from pathlib import Path
import json
from typing import Optional


DB_PATH = Path(__file__).resolve().parent / "tickets.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # Better concurrency characteristics with many reads
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            file TEXT,
            original_name TEXT,
            job_name TEXT,
            total REAL,
            category TEXT,
            batch_id TEXT,
            batch_seq INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tickets_job_name ON tickets(job_name);"
    )
    # Backward-compatible migration path: ensure 'category' column exists
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tickets);").fetchall()]
        if "category" not in cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN category TEXT;")
    except Exception:
        # Ignore migration errors; table may not exist yet
        pass
    conn.commit()


def save_ticket(
    *,
    id: str,
    file: Optional[str] = None,
    original_name: Optional[str] = None,
    job_name: Optional[str] = None,
    total: Optional[float] = None,
    batch_id: Optional[str] = None,
    batch_seq: Optional[int] = None,
    category: Optional[str] = None,
) -> None:
    """Insert or update a ticket record by id.

    The `id` should be the JSON filename stem (i.e., image filename without extension).
    Other fields are optional; this function upserts and preserves latest values.
    """
    conn = _connect()
    try:
        _init(conn)
        conn.execute(
            """
            INSERT INTO tickets (id, file, original_name, job_name, total, category, batch_id, batch_seq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                file=excluded.file,
                original_name=excluded.original_name,
                job_name=excluded.job_name,
                total=excluded.total,
                category=excluded.category,
                batch_id=excluded.batch_id,
                batch_seq=excluded.batch_seq,
                updated_at=datetime('now');
            """,
            (id, file, original_name, job_name, total, category, batch_id, batch_seq),
        )
        conn.commit()
    finally:
        conn.close()


def save_from_json_path(json_path: Path) -> None:
    """Parse a JSON result file and save fields into the DB.

    Safely ignores files without parsable JSON or without an id.
    """
    try:
        data = json.loads(Path(json_path).read_text())
    except Exception:
        return
    # id is the JSON filename stem
    stem = Path(json_path).stem
    file = data.get("file")
    original_name = data.get("original_name")
    job_name = data.get("job_name")
    total = data.get("total")
    batch_id = data.get("batch_id")
    batch_seq = data.get("batch_seq")
    category = data.get("category")
    # Only persist if we have at least one of the desired fields present
    if job_name is None and total is None:
        # still store metadata to link images to batches for future enrichment
        save_ticket(
            id=stem,
            file=file,
            original_name=original_name,
            job_name=None,
            total=None,
            batch_id=batch_id,
            batch_seq=batch_seq,
            category=category,
        )
    else:
        save_ticket(
            id=stem,
            file=file,
            original_name=original_name,
            job_name=job_name,
            total=total,
            batch_id=batch_id,
            batch_seq=batch_seq,
            category=category,
        )


def backfill_uploads(upload_dir: Path) -> None:
    """Scan an uploads directory and persist any JSON entries.

    This is idempotent and can be called repeatedly.
    """
    for f in Path(upload_dir).glob("*.json"):
        save_from_json_path(f)


def spend_by_month(conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    """Return monthly spend totals with category breakdown.

    Keys: month (YYYY-MM), total, fuel_total, other_total
    """
    own = conn is None
    if own:
        conn = _connect()
    assert conn is not None
    try:
        _init(conn)
        cur = conn.execute(
            """
            SELECT
                strftime('%Y-%m', COALESCE(updated_at, created_at)) AS month,
                ROUND(COALESCE(SUM(total), 0), 2) AS total,
                ROUND(COALESCE(SUM(CASE WHEN category = 'fuel' THEN total ELSE 0 END), 0), 2) AS fuel_total,
                ROUND(COALESCE(SUM(CASE WHEN category IS NULL OR category <> 'fuel' THEN total ELSE 0 END), 0), 2) AS other_total
            FROM tickets
            WHERE total IS NOT NULL
            GROUP BY month
            ORDER BY month DESC;
            """
        )
        rows = [
            {
                "month": r[0],
                "total": r[1],
                "fuel_total": r[2],
                "other_total": r[3],
            }
            for r in cur.fetchall()
        ]
        return rows
    finally:
        if own:
            conn.close()


def spend_by_week(conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    """Return weekly spend totals (ISO-like) with category breakdown.

    Keys: year_week (e.g., 2025-W36), total, fuel_total, other_total
    """
    own = conn is None
    if own:
        conn = _connect()
    assert conn is not None
    try:
        _init(conn)
        cur = conn.execute(
            """
            SELECT
                strftime('%Y', COALESCE(updated_at, created_at)) AS y,
                strftime('%W', COALESCE(updated_at, created_at)) AS w,
                ROUND(COALESCE(SUM(total), 0), 2) AS total,
                ROUND(COALESCE(SUM(CASE WHEN category = 'fuel' THEN total ELSE 0 END), 0), 2) AS fuel_total,
                ROUND(COALESCE(SUM(CASE WHEN category IS NULL OR category <> 'fuel' THEN total ELSE 0 END), 0), 2) AS other_total
            FROM tickets
            WHERE total IS NOT NULL
            GROUP BY y, w
            ORDER BY y DESC, w DESC;
            """
        )
        rows = []
        for y, w, total, fuel_total, other_total in cur.fetchall():
            year_week = f"{y}-W{int(w):02d}"
            rows.append(
                {
                    "year_week": year_week,
                    "total": total,
                    "fuel_total": fuel_total,
                    "other_total": other_total,
                }
            )
        return rows
    finally:
        if own:
            conn.close()
