"""Minimal Flask dashboard for uploading receipts and viewing costs."""
from flask import Flask, render_template, request, redirect, url_for
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
    files = [f.name for f in UPLOAD_DIR.glob('*')]
    return render_template('index.html', files=files)


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['receipt']
    dest = UPLOAD_DIR / file.filename
    file.save(dest)
    return redirect(url_for('classify', filename=file.filename))


@app.route('/classify/<filename>')
def classify(filename: str):
    """Run OCR on the uploaded file and display the result."""
    data = extract_receipt(UPLOAD_DIR / filename)
    return render_template('classify.html', file=filename, data=data)


if __name__ == '__main__':
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host='0.0.0.0', use_reloader=False)
