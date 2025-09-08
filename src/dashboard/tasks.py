"""RQ task(s) for OCR processing.

This module is importable by both the web process and the RQ worker.
It performs OCR, writes the JSON result, and persists fields to SQLite.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import os
from typing import Optional

# Ensure we can import sibling packages when run by RQ worker
sys.path.append(str(Path(__file__).resolve().parents[1]))  # add src/

try:
    # When imported as a package (gunicorn/rq worker)
    from .storage import save_from_json_path
except Exception:  # pragma: no cover
    from storage import save_from_json_path  # type: ignore

from ocr.receipt_ocr import extract_receipt  # type: ignore


def ocr_process(image_path_str: str) -> dict:
    """Run OCR for a single image path and persist output.

    Returns the output dictionary written to JSON for visibility in logs.
    """
    image_path = Path(image_path_str)
    data = extract_receipt(image_path)
    data.pop("status", None)

    # Derive original filename (after UUID_ prefix)
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

    try:
        save_from_json_path(json_p)
    except Exception:
        # Persisting to DB is best-effort
        pass

    return out

