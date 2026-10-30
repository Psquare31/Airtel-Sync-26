"""Document field extraction: Groq vision first, local OCR as fallback.

The local path removes the pink 'SPECIMEN' watermark by colour, runs RapidOCR,
groups boxes into rows and maps left-column labels to right-column values.
"""
from __future__ import annotations

import io
import logging
import re
import threading
import time

import numpy as np
from PIL import Image
from rapidfuzz import fuzz

from app.config import get_settings
from app.services.llm import LLMUnavailable, get_router

log = logging.getLogger("ocr")

DOC_TYPES = ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof")

FIELDS = {
    "gst_certificate": ["gstin", "legal_name", "trade_name", "constitution", "address", "date_of_liability",
                        "registration_type"],
    "udyam_certificate": ["udyam_number", "enterprise_name", "enterprise_type", "major_activity", "city", "state",
                          "date_of_registration"],
    "signatory_id": ["name", "designation", "business_name", "id_number", "valid_till"],
    "address_proof": ["document_kind", "consumer_number", "billed_to", "address", "bill_date"],
}

LABELS = {
    "gstin": "gstin",
    "legal name": "legal_name",
    "trade name": "trade_name",
    "constitution": "constitution",
    "address of principal": "address",
    "place of business": "address",
    "date of liability": "date_of_liability",
    "type of registration": "registration_type",
    "udyam reg. number": "udyam_number",
    "udyam reg number": "udyam_number",
    "udyam registration number": "udyam_number",
    "enterprise name": "enterprise_name",
    "enterprise type": "enterprise_type",
    "type of enterprise": "enterprise_type",
    "major activity": "major_activity",
    "city": "city",
    "district": "city",
    "state": "state",
    "date of registration": "date_of_registration",
    "name": "name",
    "designation": "designation",
    "for business": "business_name",
    "id no.": "id_number",
    "id no": "id_number",
    "valid till": "valid_till",
    "consumer no.": "consumer_number",
    "consumer no": "consumer_number",
    "account no.": "consumer_number",
    "billed to": "billed_to",
    "customer name": "billed_to",
    "supply address": "address",
    "service address": "address",
    "address": "address",
    "bill date": "bill_date",
    "statement date": "bill_date",
}

VISION_PROMPT = """You read Indian business KYC documents for an onboarding check.
Look at the image and return ONLY a JSON object:
{{
  "detected_type": one of "gst_certificate" | "udyam_certificate" | "signatory_id" | "address_proof" | "other",
  "title": the document title as printed,
  "fields": {{ {fields} }},
  "legible": true/false,
  "notes": short note on anything unusual (blank fields, edits, mismatched fonts), or ""
}}
Copy values exactly as printed (keep the original spelling and dates as YYYY-MM-DD if printed that way).
Use "" for any field that is blank or not present. Do not guess or correct values.
The user said this is a {doc_type}. Ignore diagonal watermark text."""


def _title_type(text: str) -> str:
    t = text.lower()
    if "gst registration" in t or ("gstin" in t and "legal name" in t):
        return "gst_certificate"
    if "udyam" in t and "enterprise" in t:
        return "udyam_certificate"
    if "signatory" in t or ("designation" in t and "id no" in t):
        return "signatory_id"
    if any(k in t for k in ("bill", "statement", "consumer", "rent agreement", "supply address")):
        return "address_proof"
    return "other"


def _prepare(image_bytes: bytes, max_width: int = 1100) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, int(img.height * max_width / img.width)))
    return img


def _text_mask(img: Image.Image) -> np.ndarray:
    """Binary image (0 = ink) with the pink watermark removed."""
    # int16, not int64: this runs on a 512 MB instance
    arr = np.asarray(img).astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    text = (arr.max(axis=2) < 150) | ((r - g < 40) & (r < 200) & (g < 200) & (b < 200))
    del arr, r, g, b
    return np.where(text, 0, 255).astype(np.uint8)


def _strip_watermark(img: Image.Image) -> np.ndarray:
    out = _text_mask(img)
    angle = _skew_angle(out)
    if abs(angle) >= 0.4:
        out = np.asarray(Image.fromarray(out).rotate(angle, resample=Image.BILINEAR, fillcolor=255, expand=False))
        out = np.where(out < 128, 0, 255).astype(np.uint8)
    return np.stack([out[: _content_bottom(out)]] * 3, axis=-1)


def _content_bottom(binary: np.ndarray) -> int:
    """Last row of the text block at the top; drops empty page and a lone footer after a big gap.
    OCR time/memory and vision tokens scale with area."""
    # > 8 dark pixels: ignores page-border lines and watermark specks that run down every row
    rows = np.where((binary == 0).sum(axis=1) > 8)[0]
    if not len(rows):
        return binary.shape[0]
    gaps = np.diff(rows)
    cut = rows.max() + 20
    big = np.where(gaps > binary.shape[0] * 0.25)[0]
    if len(big):
        cut = rows[big[0]] + 20
    return int(min(binary.shape[0], cut))


def _skew_angle(binary: np.ndarray) -> float:
    """Angle (degrees) that makes text rows horizontal: maximises row-profile variance."""
    small = Image.fromarray(binary).resize((400, max(1, int(binary.shape[0] * 400 / binary.shape[1]))))
    best, best_score = 0.0, -1.0
    for angle in np.arange(-8, 8.01, 0.5):
        rot = np.asarray(small.rotate(float(angle), fillcolor=255))
        score = float(np.var((rot < 128).sum(axis=1)))
        if score > best_score:
            best, best_score = float(angle), score
    return best


_engine = None
# one OCR at a time: two concurrent runs would not fit the free-tier memory
_ocr_lock = threading.Lock()


def _ocr_engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR

        # we deskew ourselves, so the direction classifier is dead weight
        _engine = RapidOCR(params={"Global.use_cls": False, "Global.log_level": "warning",
                                   "EngineConfig.onnxruntime.intra_op_num_threads": 2})
    return _engine


def _boxes(boxes, texts) -> list[dict]:
    out = []
    for box, txt in zip(boxes, texts):
        ys = [float(p[1]) for p in box]
        xs = [float(p[0]) for p in box]
        out.append({"y": (min(ys) + max(ys)) / 2, "x0": min(xs), "x1": max(xs), "h": max(ys) - min(ys),
                    "text": txt.strip()})
    return sorted(out, key=lambda b: (b["y"], b["x0"]))


_WATERMARK = re.compile(r"specimen|synthetic|not a valid|docum|hackathon|fictional|testing only", re.I)


def _match_label(text: str) -> str | None:
    t = text.lower().strip(" :")
    t = re.sub(r"\s+", " ", t)
    if t in LABELS:
        return LABELS[t]
    squashed = t.replace(" ", "")
    best, best_score = None, 0.0
    for label, key in LABELS.items():
        target = label.replace(" ", "")
        if squashed == target:
            return key
        # OCR slips like 'Enterprlse name'; short labels must match exactly
        if len(target) >= 8:
            score = fuzz.ratio(squashed, target)
            if score > best_score:
                best, best_score = key, score
    return best if best_score >= 88 else None


def ocr_extract(image_bytes: bytes, doc_type: str) -> dict:
    img = _prepare(image_bytes)
    arr = _strip_watermark(img)
    with _ocr_lock:
        res = _ocr_engine()(arr)
    del arr
    if not res or not res.txts:
        return {"detected_type": "other", "title": "", "fields": {}, "legible": False, "notes": "No text found"}
    boxes = _boxes(res.boxes, res.txts)
    all_text = " ".join(b["text"] for b in boxes)
    detected = _title_type(all_text)
    title = boxes[0]["text"] if boxes else ""
    boxes = [b for b in boxes if not _WATERMARK.search(b["text"])]
    for b in boxes:
        b["key"] = _match_label(b["text"])
    labels = [b for b in boxes if b["key"]]
    values = [b for b in boxes if not b["key"]]
    used: set[int] = set()
    fields: dict[str, str] = {}

    def take(b: dict) -> None:
        used.add(id(b))

    # same-row pairs first, closest in y wins (robust to slightly skewed rows)
    pairs = sorted(
        ((abs(v["y"] - lab["y"]), li, vi) for li, lab in enumerate(labels) for vi, v in enumerate(values)
         if v["x0"] > lab["x1"] and abs(v["y"] - lab["y"]) <= min(max(lab["h"], 18) * 0.9, 28)),
        key=lambda p: p[0],
    )
    row_value: dict[int, dict] = {}
    for _, li, vi in pairs:
        if li in row_value or id(values[vi]) in used:
            continue
        row_value[li] = values[vi]
        used.add(id(values[vi]))
    for li, lab in enumerate(labels):
        if li in row_value:
            v = row_value[li]
        else:  # stacked layout: value directly below the label
            below = [v for v in values if id(v) not in used and 0 < v["y"] - lab["y"] <= 3 * max(lab["h"], 18)
                     and abs(v["x0"] - lab["x0"]) < 40]
            if not below:
                continue
            v = min(below, key=lambda v: v["y"])
            take(v)
        if lab["key"] == "address" and fields.get("address"):
            fields["address"] = _join_wrapped(fields["address"], v["text"])
        else:
            fields.setdefault(lab["key"], v["text"])
        lab["value_box"] = v
    # wrapped address lines: unlabelled box aligned under the address value
    addr_lab = next((l for l in labels if l["key"] == "address" and "value_box" in l), None)
    if addr_lab:
        last = addr_lab["value_box"]
        for v in values:
            if id(v) in used:
                continue
            if 0 < v["y"] - last["y"] <= 3 * max(last["h"], 18) and abs(v["x0"] - last["x0"]) < 40:
                fields["address"] = _join_wrapped(fields["address"], v["text"])
                take(v)
                last = v
    if detected == "address_proof":
        kind = re.search(r"(electricity|water|gas|telephone|broadband)\s+bill|rent agreement|bank statement",
                         all_text, re.I)
        fields.setdefault("document_kind", kind.group(0) if kind else "")
    out = {k: fields.get(k, "") for k in FIELDS.get(doc_type, [])}
    for k, v in fields.items():
        out.setdefault(k, v)
    return {"detected_type": detected, "title": title, "fields": out, "legible": True, "notes": ""}


def _join_wrapped(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    # the specimen generator wraps mid-word ("Visakhapatnam, A" + "ndhra Pradesh")
    if b[0].islower() or (a[-1].isalpha() and len(a.split()[-1]) <= 2 and b[0].isalpha()):
        return a + b
    return f"{a} {b}"


ID_FIELDS = {"gst_certificate": "gstin", "udyam_certificate": "udyam_number"}


def _id_invalid(doc_type: str, value: str) -> bool:
    from app.services.kyc import repair_gstin
    from app.services.validators import validate_gstin, validate_udyam

    if doc_type == "gst_certificate":
        return bool(validate_gstin(repair_gstin(value)[0]))
    return bool(validate_udyam(value))


def _crosscheck_ids(data: dict, image_bytes: bytes, doc_type: str) -> None:
    """Vision models occasionally misread long IDs; if the read fails validation,
    re-read it with local OCR and keep whichever passes."""
    if not get_settings().local_ocr:
        return
    key = ID_FIELDS.get(doc_type)
    value = (data["fields"].get(key) or "") if key else ""
    if not key or not value or not _id_invalid(doc_type, value):
        return
    try:
        local = ocr_extract(image_bytes, doc_type)["fields"].get(key, "")
    except Exception as err:  # noqa: BLE001
        log.warning("OCR cross-check failed: %s", err)
        return
    if local and not _id_invalid(doc_type, local):
        log.info("%s corrected by OCR cross-check", key)
        data["fields"][key] = local
        data["extractor"] += " + ocr-check"


VISION_WAIT_S = 45  # wait out a rate-limit rather than run the heavier local OCR


def _vision(image_bytes: bytes, doc_type: str) -> dict:
    img = _prepare(image_bytes, max_width=1024)
    bottom = _content_bottom(_text_mask(img))
    if bottom < img.height:  # fewer pixels, fewer tokens, more documents per rate-limit window
        img = img.crop((0, 0, img.width, bottom))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    fields_spec = ", ".join(f'"{f}": ""' for f in FIELDS.get(doc_type, []))
    data, info = get_router().vision_json(
        VISION_PROMPT.format(fields=fields_spec, doc_type=doc_type), buf.getvalue(), "image/jpeg"
    )
    data.setdefault("fields", {})
    data["fields"] = {k: (str(v).strip() if v is not None else "") for k, v in data["fields"].items()}
    data["extractor"] = info.model
    return data


def extract(image_bytes: bytes, doc_type: str) -> dict:
    """Returns {detected_type, fields, legible, notes, extractor}."""
    router = get_router()
    if router.available():
        for attempt in range(2):
            try:
                data = _vision(image_bytes, doc_type)
                _crosscheck_ids(data, image_bytes, doc_type)
                return data
            except LLMUnavailable as err:
                wait = router.soonest_free(get_settings().vision_models)
                if attempt == 0 and wait is not None and wait <= VISION_WAIT_S:
                    log.info("vision rate-limited, retrying in %.0fs", wait)
                    time.sleep(wait + 0.5)
                    continue
                log.warning("vision unavailable, falling back to OCR: %s", err)
            except Exception as err:  # noqa: BLE001
                log.warning("vision extraction failed, falling back to OCR: %s", str(err)[:200])
            break
    if not get_settings().local_ocr:
        return {"detected_type": None, "title": "", "fields": {}, "legible": None, "extractor": "unavailable",
                "notes": "document reader busy"}
    data = ocr_extract(image_bytes, doc_type)
    data["extractor"] = "local-ocr"
    return data
