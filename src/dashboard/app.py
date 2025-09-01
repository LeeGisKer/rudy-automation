"""Minimal Flask dashboard for uploading receipts and viewing costs."""
from flask import Flask, render_template, request, redirect, url_for
from pathlib import Path

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
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
