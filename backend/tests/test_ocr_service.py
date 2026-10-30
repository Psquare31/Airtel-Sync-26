import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import ocr

ROOT = Path(__file__).resolve().parents[2]
SPECIMEN = (ROOT / "data" / "kyc_documents" / "K02_signatory_id.png").read_bytes()


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("OCR_SERVICE_KEY", "k" * 32)
    spec = importlib.util.spec_from_file_location("ocr_service_app", ROOT / "ocr_service" / "app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ocr_service_app"] = mod
    spec.loader.exec_module(mod)
    return TestClient(mod.app)


def test_service_rejects_missing_key(service):
    r = service.post("/extract", data={"doc_type": "signatory_id"}, files={"file": ("x.png", SPECIMEN, "image/png")})
    assert r.status_code == 401


def test_service_reads_a_document(service):
    r = service.post("/extract", data={"doc_type": "signatory_id"}, files={"file": ("x.png", SPECIMEN, "image/png")},
                     headers={"X-OCR-Key": "k" * 32})
    assert r.status_code == 200
    assert r.json()["fields"]["name"] == "Joseph Shah"


def test_service_rejects_oversized_upload(service):
    r = service.post("/extract", data={"doc_type": "signatory_id"},
                     files={"file": ("x.png", b"0" * (6 * 1024 * 1024 + 1), "image/png")}, headers={"X-OCR-Key": "k" * 32})
    assert r.status_code == 413


def test_api_uses_ocr_service_when_local_ocr_is_off(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_ocr", False)
    monkeypatch.setattr(s, "ocr_service_url", "https://ocr.example")
    monkeypatch.setattr(s, "ocr_service_key", "secret")
    sent = {}

    def fake_post(url, data, files, headers, timeout):
        sent.update(url=url, headers=headers, doc=data["doc_type"])
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"detected_type": "signatory_id", "fields": {"name": "Joseph Shah"}})

    monkeypatch.setattr(ocr.httpx, "post", fake_post)
    out = ocr.extract(SPECIMEN, "signatory_id")
    assert out["extractor"] == "ocr-service" and out["fields"]["name"] == "Joseph Shah"
    assert sent["url"] == "https://ocr.example/extract" and sent["headers"]["X-OCR-Key"] == "secret"


def test_documents_never_go_to_the_llm_by_default(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_ocr", False)
    monkeypatch.setattr(s, "ocr_service_url", "")
    assert s.kyc_vision is False
    called = []
    monkeypatch.setattr(ocr, "_vision", lambda *a: called.append(1))
    assert ocr.extract(SPECIMEN, "signatory_id")["extractor"] == "unavailable"
    assert not called
