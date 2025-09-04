import os, sys
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
os.environ['OCR_ASYNC'] = '0'
from dashboard.app import app

with app.test_client() as c:
    r = c.get('/')
    print('GET / status:', r.status_code)
    print('Contains title?', b'Receipts' in r.data)
