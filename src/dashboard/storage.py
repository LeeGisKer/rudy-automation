from __future__ import annotations

import sqlite3
from pathlib import Path
import json
from typing import Optional
from datetime import datetime, timedelta
import secrets


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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at);"
    )
    # Backward-compatible migration path: ensure 'category' column exists
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tickets);").fetchall()]
        if "category" not in cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN category TEXT;")
    except Exception:
        # Ignore migration errors; table may not exist yet
        pass
    # Table for temporary share links
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shares (
            token TEXT PRIMARY KEY,
            options TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_shares_expires_at ON shares(expires_at);"
    )
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


def save_from_json_path(json_path: Path, conn: Optional[sqlite3.Connection] = None) -> None:
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
    # Persist record (even if fields missing, to allow later enrichment)
    if conn is None:
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
    else:
        # Inline upsert when a connection is provided to reduce overhead
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
            (stem, file, original_name, job_name, total, category, batch_id, batch_seq),
        )


def backfill_uploads(upload_dir: Path) -> None:
    """Scan an uploads directory and persist any JSON entries.

    This is idempotent and can be called repeatedly.
    """
    conn = _connect()
    try:
        _init(conn)
        for f in Path(upload_dir).glob("*.json"):
            save_from_json_path(f, conn=conn)
        conn.commit()
    finally:
        conn.close()


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


def list_job_totals(conn: Optional[sqlite3.Connection] = None, *, only_with_values: bool = True) -> list[dict]:
    """List ticket records focusing on job_name and total.

    Returns dictionaries: id, original_name, job_name, total, created_at, updated_at.
    If only_with_values is True, filters out rows where both fields are NULL.
    """
    own = conn is None
    if own:
        conn = _connect()
    assert conn is not None
    try:
        _init(conn)
        where = "WHERE (job_name IS NOT NULL OR total IS NOT NULL)" if only_with_values else ""
        cur = conn.execute(
            f"""
            SELECT id, original_name, job_name, total, created_at, updated_at
            FROM tickets
            {where}
            ORDER BY COALESCE(updated_at, created_at) DESC
            """
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "id": r[0],
                    "original_name": r[1],
                    "job_name": r[2],
                    "total": r[3],
                    "created_at": r[4],
                    "updated_at": r[5],
                }
            )
        return rows
    finally:
        if own:
            conn.close()


def create_share(*, ttl_minutes: int = 60, options: Optional[dict] = None) -> str:
    """Create a temporary share token stored in the DB.

    Options may include future filters; currently unused but reserved.
    Returns the token string.
    """
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    conn = _connect()
    try:
        _init(conn)
        conn.execute(
            "INSERT INTO shares(token, options, expires_at) VALUES (?, ?, ?);",
            (token, json.dumps(options or {}), expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def get_share(token: str) -> Optional[dict]:
    """Return share metadata if token exists and not expired; otherwise None."""
    conn = _connect()
    try:
        _init(conn)
        cur = conn.execute("SELECT token, options, created_at, expires_at FROM shares WHERE token = ?;", (token,))
        row = cur.fetchone()
        if not row:
            return None
        expires_at = row[3]
        # Consider expired if expires_at is set and is in the past
        try:
            if expires_at and datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ") < datetime.utcnow():
                return None
        except Exception:
            # If stored date is malformed, treat as expired
            return None
        return {
            "token": row[0],
            "options": json.loads(row[1] or "{}"),
            "created_at": row[2],
            "expires_at": row[3],
        }
    finally:
        conn.close()


def get_share_items(token: str) -> Optional[list[dict]]:
    """Get the list of items for a valid share token (or None if invalid)."""
    meta = get_share(token)
    if not meta:
        return None
    # For now, ignore options and return all rows with job/total values
    return list_job_totals(only_with_values=True)
