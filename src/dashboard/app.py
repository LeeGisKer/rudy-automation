"""Minimal Flask dashboard for uploading receipts and viewing costs."""
from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename


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
 codex/optimize-code-for-raspberry-pi-9709q6
        if f.is_file():
            data = extract_receipt(f)
            entries.append({"name": f.name, "data": data})
    return render_template('index.html', files=entries)

=======
        data = extract_receipt(f)
        entries.append({"name": f.name, "data": data})
    return render_template('index.html', files=entries)




@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('receipt')
    if not file or file.filename == '':
        return redirect('/')
    dest = UPLOAD_DIR / secure_filename(file.filename)
    file.save(dest)
 codex/optimize-code-for-raspberry-pi-9709q6
    return redirect('/')
=======

main

if __name__ == '__main__':
    # Disable debug mode and reloader for lower resource use on small devices
    app.run(host='0.0.0.0', use_reloader=False)
