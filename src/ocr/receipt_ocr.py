"""OCR script for receipts using Tesseract.
Extracts store name, items, prices, and date from a receipt image.
Outputs JSON file with parsed data.
"""
from pathlib import Path
import json

from PIL import Image
import pytesseract


def extract_receipt(image_path: str) -> dict:
    """Extract text from receipt image and return basic structured data.

    The image is converted to grayscale and scaled down so that OCR runs
    efficiently on resource-constrained hardware like a Raspberry Pi.
    """
    with Image.open(image_path) as img:
        img = img.convert("L")
        img.thumbnail((2000, 2000))
        text = pytesseract.image_to_string(
            img, lang="eng", config="--psm 6"
        )
    # Placeholder parsing logic; would parse line items here
    return {"raw_text": text}


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
