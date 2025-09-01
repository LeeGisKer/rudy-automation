# Digital Automation Scaffold

This repository provides scripts, templates, and a minimal dashboard for digitizing operations of a small construction company.

## Contents
- `src/ocr/receipt_ocr.py` – Extracts raw text from receipt images using Tesseract OCR and writes JSON files.
- `src/ocr/job_assigner.py` – Command‑line helper to tag receipt line items with job IDs and save a new CSV.
- `src/dashboard/app.py` – Flask web dashboard for uploading receipts and viewing stored files.
- `excel_templates/` – CSV templates for fuel logs and job quotes that can be opened in Excel or Google Sheets.


## Setup
1. Install [Tesseract OCR](https://tesseract-ocr.github.io/) and ensure the `tesseract` command is available.
2. Install Python dependencies:
   ```bash
   pip install pillow pytesseract flask
   ```

## Usage
### Extract data from receipt images
Run the OCR script on one or more image files:
```bash
python src/ocr/receipt_ocr.py receipt1.jpg receipt2.png
```
Each image produces a `*.json` file containing the extracted text.

### Assign job IDs to line items
Provide a CSV (for example, exported from a parsed receipt) and enter job IDs interactively:
```bash
python src/ocr/job_assigner.py receipt.csv
```
The tool writes a new file `<receipt>_tagged.csv` with the added `job_id` column.

### Launch the web dashboard
Start the Flask application to upload and review receipt files:
```bash
python src/dashboard/app.py
```
Open <http://localhost:5000> in your browser and use the form to upload receipts.


### Fuel logs and quotes
Duplicate the CSV templates in `excel_templates/` to track fuel expenses and generate job quotes in Excel or Google Sheets.

## Notes
These scripts are starting points; expand them with additional parsing, data storage, or integrations as needed.
