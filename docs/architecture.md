# Digital Ecosystem Scaffold for Small Construction Company

This scaffold demonstrates how receipts, fuel logs, quotes, and dashboards
can be digitised.

## Folder Structure

```
├── docs/               # Design docs
├── excel_templates/    # CSV templates for fuel logs and quotes
├── src/
│   ├── ocr/            # Receipt OCR and job assignment scripts
│   └── dashboard/      # Flask web dashboard
```

## Tools Overview

* **OCR** – `src/ocr/receipt_ocr.py` uses [pytesseract] to convert scanned
  receipts to text and outputs JSON. `job_assigner.py` helps tag each line
  item with a job ID.
* **Fuel Log** – `excel_templates/fuel_log_template.csv` is a structured
  template that can be opened in Excel or Google Sheets for entering fuel
  expenses.
* **Quote Generator** – `excel_templates/quote_template.csv` acts as a base
  for creating job quotes. More advanced automation can read product prices
  from a database and export PDFs.
* **Dashboard** – `src/dashboard/app.py` is a minimal Flask app. It allows
  receipt uploads and lists stored files. This can be extended with cost
  breakdowns and project summaries.

## Sample Automation Snippets

### OCR Processing
```python
from pathlib import Path
from PIL import Image
import pytesseract

text = pytesseract.image_to_string(Image.open('receipt.jpg'))
Path('receipt.txt').write_text(text)
```

### Assigning Jobs per Line Item
```python
import csv
rows = list(csv.DictReader(open('receipt.csv')))
for row in rows:
    row['job_id'] = input(f"Job for {row['item']}? ")
```

### Dashboard Upload Route
```python
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['receipt']
    file.save(Path('uploads') / file.filename)
    return redirect(url_for('index'))
```

## Next Steps

* Integrate Google Vision or Microsoft OCR for improved accuracy.
* Link Google Forms to spreadsheets for quick mobile data entry.
* Generate reports with pandas or Google Data Studio.
* Consider future integration with QuickBooks for accounting.
