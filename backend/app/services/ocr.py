"""Document field extraction. KYC images are read by our own OCR and never sent to an LLM.

Order: local OCR (when the optional OCR packages are installed) -> our OCR service
(OCR_SERVICE_URL, e.g. a Hugging Face Space running ocr_service/) -> Groq vision, only
if KYC_VISION=true is set explicitly -> "reader busy".
"""
from __future__ import annotations

import io
import logging
import time

import httpx

from app.config import get_settings
from app.services.llm import LLMUnavailable, get_router
from app.services.ocr_local import (DOC_TYPES, FIELDS, _content_bottom, _prepare, _text_mask,  # noqa: F401
                                    ocr_extract)

log = logging.getLogger("ocr")

BUSY = {"detected_type": None, "title": "", "fields": {}, "legible": None, "extractor": "unavailable",
        "notes": "document reader busy"}

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


def _remote(image_bytes: bytes, doc_type: str) -> dict:
    """Our OCR service. The first call after the Space wakes can take ~60 s."""
    settings = get_settings()
    img = _prepare(image_bytes, max_width=1600)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)  # smaller upload, same OCR result
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = httpx.post(f"{settings.ocr_service_url.rstrip('/')}/extract",
                              data={"doc_type": doc_type}, files={"file": ("doc.jpg", buf.getvalue(), "image/jpeg")},
                              headers={"X-OCR-Key": settings.ocr_service_key}, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            data["extractor"] = "ocr-service"
            return data
        except (httpx.TransportError, httpx.HTTPStatusError) as err:
            last_err = err
            status = getattr(getattr(err, "response", None), "status_code", None)
            if status in (400, 401, 403, 413):
                break
            time.sleep(2)
    raise RuntimeError(f"OCR service unavailable: {last_err}")


VISION_WAIT_S = 45  # wait out a rate-limit rather than give up


def _vision(image_bytes: bytes, doc_type: str) -> dict:
    img = _prepare(image_bytes, max_width=1024)
    bottom = _content_bottom(_text_mask(img))
    if bottom < img.height:  # fewer pixels, fewer tokens
        img = img.crop((0, 0, img.width, bottom))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    fields_spec = ", ".join(f'"{f}": ""' for f in FIELDS.get(doc_type, []))
    router = get_router()
    for attempt in range(2):
        try:
            data, info = router.vision_json(
                VISION_PROMPT.format(fields=fields_spec, doc_type=doc_type), buf.getvalue(), "image/jpeg")
            data.setdefault("fields", {})
            data["fields"] = {k: (str(v).strip() if v is not None else "") for k, v in data["fields"].items()}
            data["extractor"] = info.model
            return data
        except LLMUnavailable:
            wait = router.soonest_free(get_settings().vision_models)
            if attempt == 0 and wait is not None and wait <= VISION_WAIT_S:
                time.sleep(wait + 0.5)
                continue
            raise
    raise LLMUnavailable("vision unavailable")


def reader_mode() -> str:
    """Which reader handles KYC images: 'local', 'service', 'vision' or 'none' (same order as extract)."""
    settings = get_settings()
    if settings.ocr_enabled:
        return "local"
    if settings.ocr_service_url:
        return "service"
    if settings.kyc_vision and get_router().available():
        return "vision"
    return "none"


def extract(image_bytes: bytes, doc_type: str) -> dict:
    """Returns {detected_type, fields, legible, notes, extractor}."""
    settings = get_settings()
    if settings.ocr_enabled:
        data = ocr_extract(image_bytes, doc_type)
        data["extractor"] = "local-ocr"
        return data
    if settings.ocr_service_url:
        try:
            return _remote(image_bytes, doc_type)
        except Exception as err:  # noqa: BLE001
            log.warning("OCR service failed: %s", str(err)[:200])
    if settings.kyc_vision and get_router().available():
        # opt-in only: this sends the document image to an outside LLM provider
        try:
            return _vision(image_bytes, doc_type)
        except Exception as err:  # noqa: BLE001
            log.warning("vision extraction failed: %s", str(err)[:200])
    return dict(BUSY)
