"""Minimal Flask dashboard for uploading receipts and viewing costs."""
from flask import Flask, render_template, request, redirect
from pathlib import Path

import sys

# Allow importing modules from the parent src directory
sys.path.append(str(Path(__file__).resolve().parents[1]))
from ocr.receipt_ocr import extract_receipt

app = Flask(__name__)
UPLOAD_DIR = Path('uploads')
UPLOAD_DIR.mkdir(exist_ok=True)


@app.route('/')
def index():
    entries = []
    for f in UPLOAD_DIR.glob('*'):
        data = extract_receipt(f)
        entries.append({"name": f.name, "data": data})
    return render_template('index.html', files=entries)


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['receipt']
    dest = UPLOAD_DIR / file.filename
    file.save(dest)
    return redirect('/')


if __name__ == '__main__':
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host='0.0.0.0', use_reloader=False)
