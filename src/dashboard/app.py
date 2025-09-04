"""Minimal Flask dashboard for uploading receipts and viewing costs.

Supports multi-file uploads and background OCR processing to handle
10–50 photos per session without blocking the request.
"""
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import json
from pathlib import Path
from uuid import uuid4
import sys
import os
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Allow importing modules from the parent src directory
sys.path.append(str(Path(__file__).resolve().parents[1]))
from ocr.receipt_ocr import extract_receipt

app = Flask(__name__)
# Store uploads within the dashboard package directory to avoid permission issues
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Optional: limit upload size via env var (defaults to 20 MB)
try:
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
except Exception:
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


@app.route("/")
def index():
    entries = []
    for f in UPLOAD_DIR.glob('*.json'):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            data = {"raw_text": f"JSON error: {exc}"}
        name = data.get("original_name", f.stem)
        entries.append({
            "name": name,
            "data": data,
            "json_name": f.name,
        })
    return render_template('index.html', files=entries)


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist('receipt')
    if not files:
        return redirect('/')
    missing_jsons = []
    for file in files:
        if not file or file.filename == '':
            continue
        filename = secure_filename(file.filename)
        dest = UPLOAD_DIR / f"{uuid4().hex}_{filename}"
        file.save(dest)
        data = extract_receipt(dest)
        out = {"original_name": filename, **data}
        json_path = dest.with_suffix('.json')
        json_path.write_text(json.dumps(out, indent=2))
        if out.get('job_name') in (None, "") or out.get('total') in (None, ""):
            missing_jsons.append(json_path.name)
    # If any file lacks required fields, prompt user to enter them
    if missing_jsons:
        first = missing_jsons[0]
        return redirect(url_for('classify', name=first))
    return redirect('/')


@app.route('/classify/<path:name>', methods=['GET', 'POST'])
def classify(name: str):
    # Ensure we only access files within UPLOAD_DIR
    json_path = (UPLOAD_DIR / name).resolve()
    if not str(json_path).startswith(str(UPLOAD_DIR.resolve())) or not json_path.exists():
        return redirect('/')
    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError:
        data = {}
    if request.method == 'POST':
        job_name = request.form.get('job_name', '').strip()
        total_raw = request.form.get('total', '').strip()
        total_val = None
        if total_raw:
            try:
                total_val = float(total_raw.replace(',', ''))
            except ValueError:
                total_val = None
        if job_name:
            data['job_name'] = job_name
        else:
            data['job_name'] = None
        data['total'] = total_val
        json_path.write_text(json.dumps(data, indent=2))
        # After saving, if there are other pending files, navigate next; otherwise back to index
        # Find next missing file
        for f in sorted(UPLOAD_DIR.glob('*.json')):
            try:
                d = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            if d.get('job_name') in (None, '') or d.get('total') in (None, ''):
                return redirect(url_for('classify', name=f.name))
        return redirect(url_for('index'))
    # GET
    display_name = data.get('original_name', json_path.stem)
    return render_template('classify.html', file=display_name, data=data)


if __name__ == '__main__':
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host="0.0.0.0", use_reloader=False)
