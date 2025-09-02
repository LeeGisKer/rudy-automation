"""OCR script for receipts using Tesseract.
Extracts store name, items, prices, and date from a receipt image.
Outputs JSON file with parsed data.
"""
from pathlib import Path
import json
import re

from PIL import Image, UnidentifiedImageError
import pytesseract
from pytesseract import TesseractError, TesseractNotFoundError



def extract_receipt(image_path: str) -> dict:
    """Extract text from receipt image and return structured data.

    The image is converted to grayscale and scaled down so that OCR runs
    efficiently on resource-constrained hardware like a Raspberry Pi.
    """

    try:
        with Image.open(image_path) as img:
            img = img.convert("L")
            img.thumbnail((2000, 2000))
            text = pytesseract.image_to_string(
                img, lang="eng", config="--psm 6"
            )
        job_name = _parse_job_name(text)
        total = _parse_total(text)
        return {"raw_text": text, "job_name": job_name, "total": total}
    except (UnidentifiedImageError, OSError) as exc:
        return {"raw_text": f"Image error: {exc}"}
    except (TesseractNotFoundError, TesseractError) as exc:
        return {"raw_text": f"OCR error: {exc}"}


def _parse_job_name(text: str) -> str | None:
    """Return the job name if present in the OCR text."""
    match = re.search(r"JOB\s*NAME[:#]?\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _parse_total(text: str) -> float | None:
    """Return the receipt total as a float if found."""
    candidates = re.findall(r"\bTOTAL\b\s*\$?([0-9.,]+)", text, re.IGNORECASE)
    if not candidates:
        return None
    try:
        value = candidates[-1].replace(",", "")
        return float(value)
    except ValueError:
        return None




def main(paths):
    for img in paths:
        data = extract_receipt(img)
        out_path = Path(img).with_suffix('.json')
        out_path.write_text(json.dumps(data, indent=2))
        print(f"Written {out_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python receipt_ocr.py <image1> <image2> ...")
    else:
        main(sys.argv[1:])
