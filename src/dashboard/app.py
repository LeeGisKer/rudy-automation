"""Minimal Flask dashboard for uploading receipts and viewing costs."""
from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename
import json
from pathlib import Path
import sys

# Allow importing modules from the parent src directory
sys.path.append(str(Path(__file__).resolve().parents[1]))
from ocr.receipt_ocr import extract_receipt

app = Flask(__name__)
UPLOAD_DIR = Path('uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/')
def index():
    entries = []
    for f in UPLOAD_DIR.glob('*.json'):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            data = {"raw_text": f"JSON error: {exc}"}
        entries.append({"name": f.stem, "data": data})
    return render_template('index.html', files=entries)


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('receipt')
    if not file or file.filename == '':
        return redirect('/')
    dest = UPLOAD_DIR / secure_filename(file.filename)
    file.save(dest)
    data = extract_receipt(dest)
    (dest.with_suffix('.json')).write_text(json.dumps(data, indent=2))
    return redirect('/')


if __name__ == '__main__':
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host='0.0.0.0', use_reloader=False)
