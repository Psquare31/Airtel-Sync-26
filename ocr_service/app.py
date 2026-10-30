"""Udyam Digital document reader: our own OCR as a tiny service.

Deployed as a Hugging Face Docker Space (see backend/scripts/deploy_ocr_space.py) so KYC
images are read on our own code and never sent to an LLM provider. Every request must
carry the shared X-OCR-Key. Images are processed in memory only: nothing is written to
disk and request contents are never logged.
"""
import hmac
import os

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

try:  # inside the Space, ocr_local.py sits next to this file
    import ocr_local
except ImportError:  # running from the repo
    from app.services import ocr_local

MAX_BYTES = 6 * 1024 * 1024
KEY = os.environ.get("OCR_SERVICE_KEY", "")

app = FastAPI(title="Udyam Digital OCR", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def warm() -> None:
    ocr_local.warm()


@app.get("/health")
@app.head("/health")
def health():
    return {"ok": True, "configured": bool(KEY)}


@app.post("/extract")
async def extract(doc_type: str = Form(...), file: UploadFile = File(...), x_ocr_key: str = Header(default="")):
    if not KEY or not hmac.compare_digest(x_ocr_key, KEY):
        raise HTTPException(401, "missing or wrong key")
    if doc_type not in ocr_local.DOC_TYPES:
        raise HTTPException(400, "unknown document type")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file too large")
    try:
        return ocr_local.ocr_extract(data, doc_type)
    except Exception:  # noqa: BLE001 - never echo document content back in errors
        raise HTTPException(422, "could not read this image") from None
    finally:
        del data
