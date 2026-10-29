import secrets
from datetime import timedelta

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from langgraph.types import Command
from pydantic import BaseModel

from app.config import get_settings
from app.data.loader import get_dataset
from app.db import Journey, KycDocument, audit, now, session
from app.graph.journey import get_graph
from app.services import kyc as kyc_service
from app.services import ocr
from app.services.profile import Profile
from app.services.validators import mask, normalize_id

router = APIRouter(prefix="/api/journeys", tags=["journey"])

MAX_UPLOAD = 6 * 1024 * 1024
MASKED_FIELDS = {"gstin", "udyam_number", "id_number", "consumer_number"}


class StartBody(BaseModel):
    lang: str = "en"
    partner_code: str | None = None


class ResumeBody(BaseModel):
    value: dict


def _config(jid: str) -> dict:
    return {"configurable": {"thread_id": jid}}


def view(jid: str) -> dict:
    snap = get_graph().get_state(_config(jid))
    if not snap or not snap.values:
        raise HTTPException(404, "journey not found")
    v = snap.values
    pending = None
    for task in snap.tasks:
        if task.interrupts:
            pending = task.interrupts[0].value
            break
    return {
        "journey_id": jid,
        "stage": v.get("stage"),
        "lang": v.get("lang"),
        "messages": [{"role": m["role"], "content": m["content"]} for m in v.get("messages", [])],
        "profile": v.get("profile"),
        "missing": Profile(**(v.get("profile") or {})).missing(),
        "recommendation": v.get("recommendation"),
        "explanation": v.get("explanation"),
        "quote": (pending or {}).get("quote") if (pending or {}).get("kind") == "quote" else v.get("quote"),
        "consent": v.get("consent"),
        "kyc_result": v.get("kyc_result"),
        "order_id": v.get("order_id"),
        "handoff": v.get("handoff"),
        "pending": pending,
        "model": v.get("last_model"),
    }


@router.post("")
def start(body: StartBody):
    jid = "J" + secrets.token_hex(5).upper()
    with session() as s:
        s.add(Journey(id=jid, lang=body.lang, partner_code=body.partner_code))
        s.commit()
    audit("owner" if not body.partner_code else f"partner:{body.partner_code}", "journey_started", jid)
    get_graph().invoke({"journey_id": jid, "lang": body.lang, "partner_code": body.partner_code, "messages": []},
                       _config(jid))
    return view(jid)


@router.get("/{jid}")
def get(jid: str):
    return view(jid)


@router.post("/{jid}/resume")
def resume(jid: str, body: ResumeBody):
    current = view(jid)
    if not current["pending"]:
        raise HTTPException(409, "journey is not waiting for input")
    expected = current["pending"].get("kind")
    sent = body.value.get("kind")
    if sent and sent != expected:
        raise HTTPException(409, f"journey is waiting for '{expected}', not '{sent}'")
    get_graph().invoke(Command(resume=body.value), _config(jid))
    return view(jid)


class LangBody(BaseModel):
    lang: str


@router.post("/{jid}/lang")
def set_lang(jid: str, body: LangBody):
    get_graph().update_state(_config(jid), {"lang": body.lang})
    return view(jid)


def _public_fields(fields: dict) -> dict:
    return {k: (mask(v) if k in MASKED_FIELDS else v) for k, v in fields.items()}


def _store(jid: str, doc_type: str, extraction: dict, digest: str, source: str) -> dict:
    with session() as s:
        old = [d for d in s.query(KycDocument).filter(KycDocument.journey_id == jid, KycDocument.doc_type == doc_type)]
        for d in old:
            s.delete(d)
        s.add(KycDocument(
            journey_id=jid, doc_type=doc_type, detected_type=extraction.get("detected_type"), sha256=digest,
            source=source, extractor=extraction.get("extractor", ""),
            fields={"fields": extraction.get("fields", {}), "checks": extraction.get("checks", []),
                    "legible": extraction.get("legible", True)},
            purge_after=now() + timedelta(days=30),
        ))
        s.commit()
    audit("owner", "document_received", jid, doc_type=doc_type, source=source, extractor=extraction.get("extractor"))
    return {
        "doc_type": doc_type,
        "detected_type": extraction.get("detected_type"),
        "fields": _public_fields(extraction.get("fields", {})),
        "checks": extraction.get("checks", []),
        "extractor": extraction.get("extractor"),
        "source": source,
    }


@router.post("/{jid}/documents")
async def upload_document(jid: str, doc_type: str = Form(...), file: UploadFile | None = File(None),
                          specimen: str | None = Form(None)):
    """Upload a KYC document image. The image is read in memory and discarded."""
    if doc_type not in kyc_service.DOC_LABELS:
        raise HTTPException(400, "unknown document type")
    view(jid)  # 404 if missing
    if specimen:  # demo: pick one of the hackathon specimen files
        if not specimen.isalnum() or len(specimen) > 4:
            raise HTTPException(400, "bad specimen id")
        path = get_settings().data_dir / "kyc_documents" / f"{specimen.upper()}_{doc_type}.png"
        if not path.exists():
            raise HTTPException(404, "specimen not available for this document")
        data = path.read_bytes()
    elif file:
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "file too large (max 6 MB)")
        if not (data[:8].startswith(b"\x89PNG") or data[:3] == b"\xff\xd8\xff" or data[:4] == b"RIFF"):
            raise HTTPException(415, "please upload a JPG, PNG or WebP photo")
    else:
        raise HTTPException(400, "file or specimen required")

    extraction = ocr.extract(data, doc_type)
    extraction["checks"] = [c.to_dict() for c in kyc_service.document_checks(doc_type, extraction, data)]
    digest = kyc_service.sha256(data)
    del data
    return _store(jid, doc_type, extraction, digest, "upload")


class DigiLockerBody(BaseModel):
    gstin: str | None = None
    udyam_number: str | None = None


@router.post("/{jid}/digilocker")
def digilocker(jid: str, body: DigiLockerBody):
    """Mock DigiLocker pull: issuer-signed records, so no OCR is needed."""
    view(jid)
    ds = get_dataset()
    pulled = []
    if body.gstin:
        rec = ds.gstin.get(normalize_id(body.gstin))
        if not rec:
            raise HTTPException(404, "GSTIN not found in DigiLocker")
        fields = {"gstin": rec["gstin"], "legal_name": rec["legal_name"], "trade_name": rec["trade_name"],
                  "constitution": rec["constitution"], "address": rec["principal_place_of_business"],
                  "date_of_liability": rec["registration_date"], "registration_type": "Regular"}
        pulled.append(_store(jid, "gst_certificate", {"detected_type": "gst_certificate", "fields": fields,
                                                      "extractor": "digilocker", "checks": []},
                             kyc_service.sha256(rec["gstin"].encode()), "digilocker"))
    if body.udyam_number:
        rec = ds.udyam.get(normalize_id(body.udyam_number))
        if not rec:
            raise HTTPException(404, "Udyam number not found in DigiLocker")
        fields = {"udyam_number": rec["udyam_number"], "enterprise_name": rec["enterprise_name"],
                  "enterprise_type": rec["enterprise_type"], "major_activity": rec["major_activity"],
                  "city": rec["city"], "state": rec["state"], "date_of_registration": rec["date_of_registration"]}
        pulled.append(_store(jid, "udyam_certificate", {"detected_type": "udyam_certificate", "fields": fields,
                                                        "extractor": "digilocker", "checks": []},
                             kyc_service.sha256(rec["udyam_number"].encode()), "digilocker"))
    return {"documents": pulled}


class WithdrawBody(BaseModel):
    purposes: list[str]


@router.post("/{jid}/consent/withdraw")
def withdraw_consent(jid: str, body: WithdrawBody):
    from app.services.retention import withdraw

    allowed = {"kyc_verification", "service_activation", "marketing"}
    return withdraw(jid, [p for p in body.purposes if p in allowed])


@router.get("/{jid}/documents")
def list_documents(jid: str):
    with session() as s:
        rows = s.query(KycDocument).filter(KycDocument.journey_id == jid).all()
        return [{"doc_type": r.doc_type, "source": r.source, "extractor": r.extractor,
                 "fields": _public_fields(r.fields.get("fields", {})), "checks": r.fields.get("checks", [])}
                for r in rows]
