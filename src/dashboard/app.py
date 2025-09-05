"""Minimal Flask dashboard for uploading receipts and viewing costs.

Supports multi-file uploads and background OCR processing to handle
10–50 photos per session without blocking the request.
"""
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

from pathlib import Path
import sys
import os
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Allow importing modules from the parent src directory
sys.path.append(str(Path(__file__).resolve().parents[1]))
from ocr.receipt_ocr import extract_receipt
try:
    # When running as a package (e.g., gunicorn)
    from .storage import (
        save_ticket,
        save_from_json_path,
        backfill_uploads,
        spend_by_month,
        spend_by_week,
        create_share,
        get_share,
        get_share_items,
        list_job_totals,
    )
except Exception:
    # When running as a script: fallback to local import
    from storage import (
        save_ticket,
        save_from_json_path,
        backfill_uploads,
        spend_by_month,
        spend_by_week,
        create_share,
        get_share,
        get_share_items,
        list_job_totals,
    )

app = Flask(__name__)

# Store uploads within the dashboard package directory to avoid permission issues
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Config
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}

# Background OCR executor (Tesseract runs in a separate process per call,
# so threads are acceptable and simpler cross-platform)
OCR_ASYNC = os.getenv("OCR_ASYNC", "1") == "1"
OCR_WORKERS = max(1, int(os.getenv("OCR_WORKERS", "2")))
_EXECUTOR = ThreadPoolExecutor(max_workers=OCR_WORKERS) if OCR_ASYNC else None


@app.route("/")
def index():
    # Load all JSONs, then collapse duplicates by original name
    candidates = []
    for f in UPLOAD_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            data = {"raw_text": f"JSON error: {exc}"}
        display_name = data.get("original_name", data.get("file", f.stem))
        mtime = 0.0
        try:
            mtime = f.stat().st_mtime
        except Exception:
            pass
        candidates.append({
            "id": f.stem,
            "name": display_name,
            "data": data,
            "mtime": mtime,
        })

    # Prefer completed+filled entries over processing/empty for the same original file
    grouped: dict[str, dict] = {}
    for c in candidates:
        data = c["data"]
        processing = data.get("status") == "processing"
        job_ok = bool(data.get("job_name"))
        total_ok = data.get("total") is not None
        score = (
            0 if processing else 1,                 # prefer not processing
            (1 if job_ok else 0) + (1 if total_ok else 0),  # prefer both fields present
            c["mtime"],                              # prefer newer
        )
        key = c["name"]
        prev = grouped.get(key)
        if not prev or score > prev["_score"]:
            grouped[key] = {**c, "_score": score}

    entries = [{k: v for k, v in item.items() if k != "_score"} for item in grouped.values()]

    # Build batch groups: latest batches first, entries ordered by batch_seq
    def _parse_batch_ts(bid: str | None) -> float:
        if not bid:
            return -1.0
        try:
            ts = bid.split("_", 1)[0]
            dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
            return dt.timestamp()
        except Exception:
            return 0.0

    groups_map: dict[str | None, dict] = {}
    for e in entries:
        data = e.get("data", {})
        bid = data.get("batch_id")
        g = groups_map.setdefault(bid, {"id": bid, "items": [], "batch_total": data.get("batch_total")})
        # Keep the max batch_total if present
        if data.get("batch_total") and (not g.get("batch_total") or data.get("batch_total") > g.get("batch_total")):
            g["batch_total"] = data.get("batch_total")
        g["items"].append(e)

    # Order entries within group
    for g in groups_map.values():
        g["items"].sort(key=lambda x: (x.get("data", {}).get("batch_seq") or 0, x["name"]))
        # Precompute title
        if g["id"]:
            ts = _parse_batch_ts(g["id"]) or 0
            try:
                title = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                title = g["id"]
            g["title"] = title
        else:
            g["title"] = "Other"

    # Sort groups: latest timestamp first; None (Other) last
    groups = sorted(groups_map.values(), key=lambda g: (_parse_batch_ts(g["id"]) if g["id"] else -1.0), reverse=True)

    # Auto-scan for orphan images without JSON and schedule processing
    if OCR_ASYNC:
        _bootstrap_pending_jobs()

    # Backfill DB so saved tickets are queryable in the future
    try:
        backfill_uploads(UPLOAD_DIR)
    except Exception:
        pass

    any_processing = any(e["data"].get("status") == "processing" for e in entries)
    return render_template("index.html", groups=groups, any_processing=any_processing)


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("receipt") or []
    # Collect only valid image files
    valid: list[tuple] = []
    for file in files:
        if not file or file.filename == "":
            continue
        filename = secure_filename(file.filename)
        if Path(filename).suffix.lower() not in ALLOWED_EXT:
            continue
        valid.append((file, filename))
    if not valid:
        return redirect("/")

    # Tag this batch and assign sequence numbers
    batch_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + f"_{uuid4().hex[:6]}"
    batch_total = len(valid)

    for idx, (file, filename) in enumerate(valid, start=1):
        dest = UPLOAD_DIR / f"{uuid4().hex}_{filename}"
        file.save(dest)
        meta = {"batch_id": batch_id, "batch_seq": idx, "batch_total": batch_total, "original_name": filename}
        if OCR_ASYNC:
            _schedule_ocr(dest, meta)
        else:
            data = extract_receipt(dest)
            out = {**meta, **data}
            json_path = dest.with_suffix(".json")
            json_path.write_text(json.dumps(out, indent=2))
            # Persist to DB if any field present
            try:
                save_from_json_path(json_path)
            except Exception:
                pass
            if not out.get("job_name") or out.get("total") is None:
                return redirect(url_for("classify", name=json_path.stem))
    return redirect("/")


@app.route("/classify/<name>", methods=["GET", "POST"])
def classify(name: str):
    json_path = UPLOAD_DIR / f"{name}.json"
    if not json_path.exists():
        return redirect("/")
    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError:
        data = {}

    # Do not allow edits while processing; show form after completion
    if data.get("status") == "processing" and request.method == "GET":
        return redirect("/")

    if request.method == "POST":
        job_name = (request.form.get("job_name") or "").strip() or None
        total_str = (request.form.get("total") or "").strip()
        category_raw = (request.form.get("category") or "").strip().lower()
        category = "fuel" if category_raw == "fuel" else None
        try:
            total_val = float(total_str.replace(",", "")) if total_str else None
        except ValueError:
            total_val = None

        data["job_name"] = job_name
        data["total"] = total_val
        if category:
            data["category"] = category
        else:
            data.pop("category", None)
        data.pop("status", None)
        json_path.write_text(json.dumps(data, indent=2))
        # Persist classification edits to DB
        try:
            save_ticket(
                id=name,
                file=data.get("file"),
                original_name=data.get("original_name"),
                job_name=job_name,
                total=total_val,
                batch_id=data.get("batch_id"),
                batch_seq=data.get("batch_seq"),
                category=category,
            )
        except Exception:
            pass
        return redirect("/")

    return render_template("classify.html", file=name, data=data)


@app.route("/reports")
def reports():
    # Ensure DB has latest entries
    try:
        backfill_uploads(UPLOAD_DIR)
    except Exception:
        pass
    monthly = []
    weekly = []
    try:
        monthly = spend_by_month()
        weekly = spend_by_week()
    except Exception:
        pass
    return render_template("reports.html", monthly=monthly, weekly=weekly)


@app.route("/share/new")
def share_new():
    """Create a temporary share link to view job/total data.

    Optional query param `ttl` specifies minutes until expiration (default 60).
    """
    try:
        ttl = int(request.args.get("ttl", "60"))
        ttl = max(1, min(ttl, 7 * 24 * 60))  # clamp to [1 minute, 7 days]
    except Exception:
        ttl = 60
    token = create_share(ttl_minutes=ttl)
    return redirect(url_for("share_view", token=token))


@app.route("/share/<token>")
def share_view(token: str):
    meta = get_share(token)
    if not meta:
        return render_template("share.html", token=token, expired=True, items=[], meta=None)
    # Ensure DB has latest entries from uploads
    try:
        backfill_uploads(UPLOAD_DIR)
    except Exception:
        pass
    items = get_share_items(token) or []
    return render_template("share.html", token=token, expired=False, items=items, meta=meta)


def _schedule_ocr(image_path: Path, meta: dict | None = None) -> None:
    """Create a placeholder JSON and schedule background OCR."""
    json_path = image_path.with_suffix(".json")
    # Derive original filename (after UUID_ prefix)
    n = image_path.name
    original_name = n.split("_", 1)[1] if "_" in n else n
    placeholder = {
        "status": "processing",
        "file": image_path.name,
        "original_name": original_name,
        "started_at": datetime.utcnow().isoformat() + "Z",
    }
    if meta:
        placeholder.update({k: v for k, v in meta.items() if k in {"batch_id", "batch_seq", "batch_total", "original_name"}})
    json_path.write_text(json.dumps(placeholder, indent=2))
    assert _EXECUTOR is not None
    _EXECUTOR.submit(_process_and_write, image_path)


def _process_and_write(image_path: Path) -> None:
    try:
        data = extract_receipt(image_path)
        # Clear processing status on success
        data.pop("status", None)
        n = image_path.name
        original_name = n.split("_", 1)[1] if "_" in n else n
        # Carry over batch metadata from placeholder if present
        meta: dict = {}
        try:
            prev = json.loads(image_path.with_suffix(".json").read_text())
            for k in ("batch_id", "batch_seq", "batch_total"):
                if k in prev:
                    meta[k] = prev[k]
        except Exception:
            pass
        out = {"file": image_path.name, "original_name": original_name, **meta, **data}
        json_p = image_path.with_suffix(".json")
        json_p.write_text(json.dumps(out, indent=2))
        # Persist to DB
        try:
            save_from_json_path(json_p)
        except Exception:
            pass
    except Exception as exc:
        error = {"status": "error", "error": str(exc), "file": image_path.name}
        image_path.with_suffix(".json").write_text(json.dumps(error, indent=2))


def _bootstrap_pending_jobs() -> None:
    """On each index view, (re)schedule any images missing results."""
    assert _EXECUTOR is not None
    for img in UPLOAD_DIR.iterdir():
        if img.is_file() and img.suffix.lower() in ALLOWED_EXT:
            j = img.with_suffix(".json")
            if not j.exists():
                _schedule_ocr(img)
                continue
            try:
                meta = json.loads(j.read_text())
            except Exception:
                continue
            if meta.get("status") == "processing":
                # Re-enqueue if previous run crashed
                _EXECUTOR.submit(_process_and_write, img)


if __name__ == "__main__":
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host="0.0.0.0", use_reloader=False)
