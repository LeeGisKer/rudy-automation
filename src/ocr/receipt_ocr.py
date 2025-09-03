"""OCR script for receipts using Tesseract.
Extracts store name, items, prices, and date from a receipt image.
Outputs JSON file with parsed data.
"""
from pathlib import Path
import json
<<<<<<< ours
import re
<<<<<<< ours
from typing import Optional, List, Tuple, Dict, Any
import os
=======
>>>>>>> theirs
=======
>>>>>>> theirs

from PIL import Image, UnidentifiedImageError, ImageOps, ImageFilter, ExifTags
import pytesseract
from pytesseract import TesseractError, TesseractNotFoundError
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _HAS_CV = True
except Exception:
    _HAS_CV = False



def extract_receipt(image_path: str) -> dict:
    """Extract text from receipt image and return basic structured data.
    """Extract text from receipt image and return basic structured data.

    The image is converted to grayscale and scaled down so that OCR runs
    efficiently on resource-constrained hardware like a Raspberry Pi.
    """

    try:
<<<<<<< ours
        psm = os.getenv("OCR_PSM", "6")
        base_cfg = f"--oem 3 --psm {psm}"

        pil_base = _load_prepare_image(Path(image_path))
        variants = _generate_variants(pil_base)
        best_label, best_text, best_stats = _choose_best_variant(variants, base_cfg)

        if os.getenv("DEBUG_OCR"):
            _export_debug_variants(variants, Path(image_path).with_suffix(""))

        job_name = _parse_job_name(best_text)
        total = _parse_total(best_text)
        if total is None:
            # Try ROI-based extraction using word coordinates
            total = _extract_total_via_data(variants, base_cfg)
        if job_name is None:
            job_name = _extract_jobname_via_data(variants, base_cfg)
        return {"raw_text": best_text, "job_name": job_name, "total": total, "variant": best_label, "stats": best_stats}
=======
        with Image.open(image_path) as img:
            img = img.convert("L")
            img.thumbnail((2000, 2000))
            text = pytesseract.image_to_string(
                img, lang="eng", config="--psm 6"
            )
<<<<<<< ours
        job_name = _parse_job_name(text)
        total = _parse_total(text)
        return {"raw_text": text, "job_name": job_name, "total": total}
>>>>>>> theirs
=======
        return {"raw_text": text}
>>>>>>> theirs
    except (UnidentifiedImageError, OSError) as exc:
        return {"raw_text": f"Image error: {exc}"}
    except (TesseractNotFoundError, TesseractError) as exc:
        return {"raw_text": f"OCR error: {exc}"}


<<<<<<< ours
<<<<<<< ours
def _auto_orient(img: Image.Image) -> Image.Image:
    try:
        exif = img.getexif()
        if not exif:
            return img
        # Find orientation tag id
        orientation_tag = None
        for k, v in ExifTags.TAGS.items():
            if v == 'Orientation':
                orientation_tag = k
                break
        if orientation_tag and orientation_tag in exif:
            return ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def _load_prepare_image(path: Path) -> Image.Image:
    with Image.open(path) as pil:
        pil = _auto_orient(pil)
        pil = _resize_long_edge(pil, 1800)
        pil = pil.convert("RGB")
        # If OpenCV available, try orientation detection (OSD) when EXIF is missing
        if _HAS_CV and not _has_exif_orientation(path):
            try:
                gray = ImageOps.grayscale(pil)
                arr = np.array(gray)
                angle = _osd_rotation(arr)
                if angle:
                    pil = pil.rotate(angle, expand=True)
            except Exception:
                pass
        # Optional perspective correction/cropping to the receipt region
        if _HAS_CV and not os.getenv("OCR_DISABLE_CROP"):
            try:
                corrected = _crop_receipt_region(pil)
                if corrected is not None:
                    pil = corrected
            except Exception:
                pass
        return pil


def _has_exif_orientation(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return False
            for k, v in ExifTags.TAGS.items():
                if v == 'Orientation' and k in exif:
                    return True
    except Exception:
        return False
    return False


def _generate_variants(pil: Image.Image) -> List[Tuple[str, object]]:
    """Return a list of (label, image) variants to try with Tesseract."""
    variants: List[Tuple[str, object]] = []

    # Baseline grayscale, no threshold
    gray_pil = ImageOps.autocontrast(pil.convert("L"))
    variants.append(("pil_gray", gray_pil))

    # PIL Otsu
    arr = np.array(gray_pil)
    thr = _otsu_threshold(arr)
    bw_arr = (arr > thr).astype('uint8') * 255
    variants.append(("pil_otsu", Image.fromarray(bw_arr)))

    if _HAS_CV and not os.getenv("OCR_DISABLE_CV"):
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # CLAHE + adaptive threshold (original approach)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray_c = clahe.apply(gray)
        gray_c = cv2.bilateralFilter(gray_c, d=5, sigmaColor=45, sigmaSpace=45)
        bw_adapt = cv2.adaptiveThreshold(
            gray_c, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
        )
        variants.append(("cv_adapt", bw_adapt))

        # CLAHE + global Otsu (less aggressive)
        blur = cv2.GaussianBlur(gray_c, (5, 5), 0)
        _, bw_otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(("cv_otsu", bw_otsu))

        # Deskew + light sharpen without morphology
        angle = _estimate_skew_angle(bw_adapt)
        if abs(angle) > 0.5:
            deskewed = _rotate_bound(bw_adapt, -angle)
        else:
            deskewed = bw_adapt
        sharp = cv2.GaussianBlur(deskewed, (0, 0), 1.0)
        sharp = cv2.addWeighted(sharp, 1.4, sharp, -0.4, 0)
        variants.append(("cv_adapt_deskew_sharp", sharp))

    return variants


def _osd_rotation(gray_arr: 'np.ndarray') -> int:
    """Return clockwise rotation (0, 90, 180, 270) based on Tesseract OSD."""
    try:
        osd = pytesseract.image_to_osd(gray_arr)
        # osd contains line like: Rotate: 90
        m = re.search(r"Rotate:\s*(\d+)", osd)
        if m:
            rot = int(m.group(1)) % 360
            # PIL.rotate uses counter-clockwise; we want to correct clockwise
            return (360 - rot) % 360
    except Exception:
        pass
    return 0


def _ocr_stats(image, config: str):
    try:
        data = pytesseract.image_to_data(image, lang="eng", config=config, output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data.get('conf', []) if str(c).isdigit() and int(c) >= 0]
        text = "\n".join([t for t in data.get('text', []) if t and t.strip()])
        mean_conf = sum(confs) / len(confs) if confs else 0.0
        n_words = sum(1 for t in data.get('text', []) if t and t.strip())
        return text, {"mean_conf": round(mean_conf, 2), "n_words": n_words, "len": len(text)}
    except Exception:
        # Fallback to simple extraction if data API fails
        text = pytesseract.image_to_string(image, lang="eng", config=config)
        return text, {"mean_conf": 0.0, "n_words": len(text.split()), "len": len(text)}


def _choose_best_variant(variants: List[Tuple[str, object]], config: str):
    best = ("", "", {"mean_conf": 0.0, "n_words": 0, "len": 0})
    best_score = -1.0
    for label, img in variants:
        text, stats = _ocr_stats(img, config)
        # Composite score: confidence primary, length secondary
        score = stats["mean_conf"] + min(stats["len"], 5000) / 5000.0
        if score > best_score:
            best_score = score
            best = (label, text, stats)
    return best


def _extract_total_via_data(variants: List[Tuple[str, object]], config: str) -> Optional[float]:
    """Search for TOTAL-like tokens and OCR the numeric ROI to the right.

    Prefers the bottom-most TOTAL line and ignores SUBTOTAL.
    """
    label_tokens = {"TOTAL", "GRAND", "DUE", "AMOUNT", "BALANCE"}
    best_candidate = None  # (img, x_right, y0, y1)

    for _, img in variants:
        try:
            data = pytesseract.image_to_data(img, lang="eng", config=config, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        lines = _group_lines(data)
        for line in lines:
            words_upper = [w['text'].upper() for w in line['words']]
            line_str = " ".join(words_upper)
            if "SUBTOTAL" in line_str:
                continue
            if any(tok in words_upper or tok in line_str for tok in label_tokens) or "TOTAL" in line_str:
                # Find the right bound of the label token(s)
                idxs = [i for i, w in enumerate(words_upper) if (w in label_tokens or "TOTAL" in w)]
                if not idxs:
                    continue
                last_idx = idxs[-1]
                last_word = line['words'][last_idx]
                x_right = last_word['left'] + last_word['width']
                # Scan for any explicit number tokens on the same line first
                num = _parse_number_from_words(line['words'][last_idx+1:])
                if num is not None:
                    return num
                # Otherwise, define a ROI to the right for OCR
                y0 = min(w['top'] for w in line['words'])
                h_line = max(w['height'] for w in line['words'])
                y0 = max(0, y0 - int(h_line * 0.3))
                y1 = y0 + int(h_line * 2.0)
                best_candidate = (img, x_right, y0, y1)

    if best_candidate is None:
        return None

    img, x_right, y0, y1 = best_candidate
    # Crop ROI and OCR with numeric whitelist
    if isinstance(img, Image.Image):
        W, H = img.size
        roi = img.crop((min(x_right, W-1), max(0, y0), min(x_right + int(W*0.4), W), min(y1, H)))
    else:
        H, W = img.shape[:2]
        x0 = min(x_right, W-1)
        x1 = min(x_right + int(W*0.4), W)
        y0c = max(0, y0)
        y1c = min(y1, H)
        roi = img[y0c:y1c, x0:x1]
    num_cfg = config + " -c tessedit_char_whitelist=0123456789.,:$"
    try:
        txt = pytesseract.image_to_string(roi, lang="eng", config=num_cfg)
        m = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})", txt)
        if m:
            return float(m.group(1).replace(',', ''))
    except Exception:
        return None
    return None


def _parse_number_from_words(words: List[Dict[str, Any]]) -> Optional[float]:
    joined = " ".join((w['text'] or '') for w in words)
    m = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})", joined)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except Exception:
            return None
    return None


def _group_lines(data: Dict[str, List]) -> List[Dict[str, Any]]:
    n = len(data.get('text', []))
    lines: Dict[Tuple[int, int, int], List[int]] = {}
    for i in range(n):
        if not (data['text'][i] and str(data.get('conf', [0])[i]).isdigit()):
            continue
        key = (data.get('block_num', [0])[i], data.get('par_num', [0])[i], data.get('line_num', [0])[i])
        lines.setdefault(key, []).append(i)
    out: List[Dict[str, Any]] = []
    for key, idxs in sorted(lines.items(), key=lambda kv: min(data['top'][i] for i in kv[1])):
        words = [
            {
                'text': data['text'][i],
                'left': data['left'][i],
                'top': data['top'][i],
                'width': data['width'][i],
                'height': data['height'][i],
            }
            for i in sorted(idxs, key=lambda i: data['left'][i])
        ]
        out.append({'words': words})
    return out


def _extract_jobname_via_data(variants: List[Tuple[str, object]], config: str) -> Optional[str]:
    """Locate JOB NAME or PO/JOB NAME label and read the value to the right or next line."""
    label_patterns = [
        ["PO/JOB", "NAME"],
        ["JOB", "NAME"],
        ["PO", "JOB", "NAME"],
    ]
    for _, img in variants:
        try:
            data = pytesseract.image_to_data(img, lang="eng", config=config, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        lines = _group_lines(data)
        for li, line in enumerate(lines):
            tokens = [w['text'].upper() for w in line['words']]
            tokens_norm = [t.replace('PO/ JOB', 'PO/JOB').replace('PO /JOB', 'PO/JOB') for t in tokens]
            for pat in label_patterns:
                idx = _find_subsequence(tokens_norm, pat)
                if idx is not None:
                    last_idx = idx + len(pat) - 1
                    value = _text_right_of_index(line, last_idx)
                    if value:
                        return _clean_job_name(value)
                    if li + 1 < len(lines):
                        value2 = _text_right_of_index(lines[li + 1], -1)
                        if value2:
                            return _clean_job_name(value2)
    return None


def _find_subsequence(seq: List[str], pat: List[str]) -> Optional[int]:
    for i in range(len(seq) - len(pat) + 1):
        ok = True
        for j, p in enumerate(pat):
            if p not in seq[i + j]:  # tolerate minor OCR noise
                ok = False
                break
        if ok:
            return i
    return None


def _text_right_of_index(line: Dict[str, Any], index: int) -> str:
    words = line['words']
    if not words:
        return ""
    if 0 <= index < len(words):
        x_min = words[index]['left'] + words[index]['width']
        right_words = [w['text'] for w in words if w['left'] > x_min]
    else:
        right_words = [w['text'] for w in words]
    text = " ".join(t for t in right_words if t and t.strip())
    return text.strip(" :#-|")


def _clean_job_name(s: str) -> str:
    s = re.sub(r"<[^>]*>", "", s)
    s = s.strip()
    m = re.match(r"([A-Za-z0-9\-_.]+)", s)
    return m.group(1) if m else s


def _export_debug_variants(variants: List[Tuple[str, object]], stem: Path):
    try:
        outdir = Path(os.getenv("DEBUG_OCR_DIR", "/tmp/ocr_debug"))
        outdir.mkdir(parents=True, exist_ok=True)
        for label, img in variants:
            p = outdir / f"{stem.name}_{label}.png"
            if isinstance(img, Image.Image):
                img.save(p)
            else:
                cv2.imwrite(str(p), img)
    except Exception:
        pass


def _resize_long_edge(img: Image.Image, target: int) -> Image.Image:
    w, h = img.size
    long = max(w, h)
    if long <= target:
        return img
    scale = target / float(long)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)


def _otsu_threshold(arr: 'np.ndarray') -> int:
    # Manual Otsu for fallback
    hist, _ = np.histogram(arr, bins=256, range=(0, 255))
    total = arr.size
    sum_total = np.dot(np.arange(256), hist)
    sum_b, w_b, var_max, threshold = 0.0, 0.0, 0.0, 0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > var_max:
            var_max = var_between
            threshold = t
    return threshold


def _estimate_skew_angle(bw: 'np.ndarray') -> float:
    try:
        edges = cv2.Canny(bw, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180.0, 200)
        if lines is None:
            return 0.0
        angles = []
        for rho_theta in lines:
            rho, theta = rho_theta[0]
            angle = (theta * 180 / np.pi) - 90
            # Keep near-horizontal lines only
            if -45 < angle < 45:
                angles.append(angle)
        if not angles:
            return 0.0
        return float(np.median(angles))
    except Exception:
        return 0.0


def _rotate_bound(image: 'np.ndarray', angle: float) -> 'np.ndarray':
    (h, w) = image.shape[:2]
    cX, cY = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D((cX, cY), angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    nW = int((h * sin) + (w * cos))
    nH = int((h * cos) + (w * sin))
    M[0, 2] += (nW / 2) - cX
    M[1, 2] += (nH / 2) - cY
    return cv2.warpAffine(image, M, (nW, nH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _crop_receipt_region(pil: Image.Image) -> Optional[Image.Image]:
    """Find the largest document-like contour and apply a top-down transform.

    Returns None if no plausible contour is found.
    """
    try:
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        ratio = 1000.0 / max(img.shape[:2])
        resized = cv2.resize(img, (int(img.shape[1] * ratio), int(img.shape[0] * ratio)))
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(gray, 50, 150)
        # Close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edged = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        screen_cnt = None
        for c in contours[:10]:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            area = cv2.contourArea(approx)
            if len(approx) == 4 and area > 1000:
                screen_cnt = approx
                break
        if screen_cnt is None:
            return None
        # Scale contour back to original size
        screen_cnt = (screen_cnt / ratio).reshape(4, 2)
        warped = _four_point_transform(cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR), screen_cnt)
        warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)
        return Image.fromarray(warped_rgb)
    except Exception:
        return None


def _order_points(pts: 'np.ndarray') -> 'np.ndarray':
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def _four_point_transform(image: 'np.ndarray', pts: 'np.ndarray') -> 'np.ndarray':
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(max(widthA, widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(max(heightA, heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


def _parse_job_name(text: str) -> Optional[str]:
=======
def _parse_job_name(text: str) -> str | None:
>>>>>>> theirs
    """Return the job name if present in the OCR text."""
    match = re.search(r"JOB\s*NAME[:#]?\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


<<<<<<< ours
def _parse_total(text: str) -> Optional[float]:
    """Return the receipt total as a float if found.

    Looks for variations like TOTAL, GRAND TOTAL, AMOUNT DUE, BALANCE DUE.
    """
    patterns = [
        r"\b(?:GRAND\s*)?TOTAL\b\s*[:\-]?\s*\$?([0-9][0-9.,]*)",
        r"\bAMOUNT\s*DUE\b\s*[:\-]?\s*\$?([0-9][0-9.,]*)",
        r"\bBALANCE\s*DUE\b\s*[:\-]?\s*\$?([0-9][0-9.,]*)",
        r"\bTOTAL\s*DUE\b\s*[:\-]?\s*\$?([0-9][0-9.,]*)",
    ]
    candidates = []
    for pat in patterns:
        candidates.extend(re.findall(pat, text, re.IGNORECASE))
=======
def _parse_total(text: str) -> float | None:
    """Return the receipt total as a float if found."""
    candidates = re.findall(r"\bTOTAL\b\s*\$?([0-9.,]+)", text, re.IGNORECASE)
>>>>>>> theirs
    if not candidates:
        return None
    try:
        value = candidates[-1].replace(",", "")
        return float(value)
    except ValueError:
        return None


=======
>>>>>>> theirs


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
