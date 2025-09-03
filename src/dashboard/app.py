"""Minimal Flask dashboard for uploading receipts and viewing costs.

Now supports multi-file uploads and background OCR processing to handle
10–50 photos per session without blocking the request.
"""
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import json
from pathlib import Path
from uuid import uuid4
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Allow importing modules from the parent src directory
sys.path.append(str(Path(__file__).resolve().parents[1]))
from ocr.receipt_ocr import extract_receipt

app = Flask(__name__)

# Store uploads within the dashboard package directory
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Config
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp', '.gif'}

# Background OCR executor (tesseract runs in a separate process per call,
# so threads are acceptable and simpler cross‑platform)
OCR_ASYNC = os.getenv("OCR_ASYNC", "1") == "1"
OCR_WORKERS = max(1, int(os.getenv("OCR_WORKERS", "2")))
_EXECUTOR = ThreadPoolExecutor(max_workers=OCR_WORKERS) if OCR_ASYNC else None


@app.route('/')
def index():
    entries = []
    for f in sorted(UPLOAD_DIR.glob('*.json')):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            data = {"raw_text": f"JSON error: {exc}"}
        entries.append({"name": f.stem, "data": data})
    # Auto-scan for orphan images without JSON and schedule processing
    if OCR_ASYNC:
        _bootstrap_pending_jobs()
    any_processing = any(e["data"].get("status") == "processing" for e in entries)
    return render_template('index.html', files=entries, any_processing=any_processing)


@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('receipt') or []
    if not files:
        return redirect('/')
    for file in files:
        if not file or file.filename == '':
            continue
        filename = secure_filename(file.filename)
        if Path(filename).suffix.lower() not in ALLOWED_EXT:
            continue
        dest = UPLOAD_DIR / f"{uuid4().hex}_{filename}"
        file.save(dest)
        if OCR_ASYNC:
            _schedule_ocr(dest)
        else:
            data = extract_receipt(dest)
            json_path = dest.with_suffix('.json')
            json_path.write_text(json.dumps(data, indent=2))
            if not data.get('job_name') or data.get('total') is None:
                return redirect(url_for('classify', name=json_path.stem))
    return redirect('/')


@app.route('/classify/<name>', methods=['GET', 'POST'])
def classify(name: str):
    json_path = UPLOAD_DIR / f"{name}.json"
    if not json_path.exists():
        return redirect('/')
    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError:
        data = {}

    # Do not allow edits while processing; show form after completion
    if data.get('status') == 'processing' and request.method == 'GET':
        return redirect('/')

    if request.method == 'POST':
        job_name = (request.form.get('job_name') or '').strip() or None
        total_str = (request.form.get('total') or '').strip()
        try:
            total_val = float(total_str.replace(',', '')) if total_str else None
        except ValueError:
            total_val = None

        data['job_name'] = job_name
        data['total'] = total_val
        data.pop('status', None)
        json_path.write_text(json.dumps(data, indent=2))
        return redirect('/')

    return render_template('classify.html', file=name, data=data)


def _schedule_ocr(image_path: Path) -> None:
    """Create a placeholder JSON and schedule background OCR."""
    json_path = image_path.with_suffix('.json')
    placeholder = {
        "status": "processing",
        "file": image_path.name,
        "started_at": datetime.utcnow().isoformat() + "Z"
    }
    json_path.write_text(json.dumps(placeholder, indent=2))
    assert _EXECUTOR is not None
    _EXECUTOR.submit(_process_and_write, image_path)


def _process_and_write(image_path: Path) -> None:
    try:
        data = extract_receipt(image_path)
        # Clear processing status on success
        data.pop('status', None)
        out = data | {"file": image_path.name}
        image_path.with_suffix('.json').write_text(json.dumps(out, indent=2))
    except Exception as exc:
        error = {"status": "error", "error": str(exc), "file": image_path.name}
        image_path.with_suffix('.json').write_text(json.dumps(error, indent=2))


def _bootstrap_pending_jobs() -> None:
    """On each index view, (re)schedule any images missing results."""
    assert _EXECUTOR is not None
    for img in UPLOAD_DIR.iterdir():
        if img.is_file() and img.suffix.lower() in ALLOWED_EXT:
            j = img.with_suffix('.json')
            if not j.exists():
                _schedule_ocr(img)
                continue
            try:
                meta = json.loads(j.read_text())
            except Exception:
                continue
            if meta.get('status') == 'processing':
                # Re-enqueue if previous run crashed
                _EXECUTOR.submit(_process_and_write, img)


if __name__ == '__main__':
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host='0.0.0.0', use_reloader=False)
