"""Catalogue, mock registries, orders/tracker and voice."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.data.loader import get_dataset
from app.services import orders
from app.services.advisor import LANG_NAMES
from app.services.llm import LLMUnavailable, get_router
from app.services.validators import normalize_id, validate_gstin, validate_udyam

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/catalogue")
def catalogue():
    return [p.to_dict() for p in get_dataset().products.values()]


@router.get("/registry/gstin/{gstin}")
def gstin_lookup(gstin: str):
    """Mock of the public GST taxpayer search."""
    g = normalize_id(gstin)
    problems = validate_gstin(g)
    if problems:
        return {"valid_format": False, "problems": problems, "found": False}
    rec = get_dataset().gstin.get(g)
    if not rec:
        return {"valid_format": True, "found": False}
    return {"valid_format": True, "found": True, "legal_name": rec["legal_name"], "trade_name": rec["trade_name"],
            "constitution": rec["constitution"], "state": rec["state"], "status": rec["status"],
            "registration_date": rec["registration_date"]}


@router.get("/registry/udyam/{number}")
def udyam_lookup(number: str):
    u = normalize_id(number)
    problems = validate_udyam(u)
    if problems:
        return {"valid_format": False, "problems": problems, "found": False}
    rec = get_dataset().udyam.get(u)
    if not rec:
        return {"valid_format": True, "found": False}
    return {"valid_format": True, "found": True, **{k: rec[k] for k in
            ("enterprise_name", "enterprise_type", "major_activity", "state", "city", "date_of_registration")}}


@router.get("/orders/{order_id}")
def get_order(order_id: str):
    order = orders.get_order(order_id)
    if not order:
        raise HTTPException(404, "order not found")
    return orders.view(order)


@router.post("/orders/{order_id}/advance")
def advance_order(order_id: str):
    if not get_settings().demo_mode:
        raise HTTPException(403, "demo only")
    order = orders.advance(order_id.upper())
    if not order:
        raise HTTPException(404, "order not found")
    return orders.view(order)


class AskBody(BaseModel):
    question: str
    lang: str = "en"


@router.post("/orders/{order_id}/ask")
def ask_order(order_id: str, body: AskBody):
    """Answers 'where is my order' from the deterministic status; the LLM only rephrases."""
    order = orders.get_order(order_id)
    if not order:
        raise HTTPException(404, "order not found")
    v = orders.view(order)
    facts = (f"Order {v['id']}. Current step: {v['current']}. Expected all-active date: {v['eta']}. "
             f"Install slot: {v['install_slot'] or 'to be confirmed'}. Services: "
             + ", ".join(f"{i['name']} ({i['status']})" for i in v["items"]))
    answer = f"{v['current']}. Everything should be active by {v['eta']}."
    model = "rules"
    try:
        text, info = get_router().chat([
            {"role": "system", "content": f"Answer the customer's question in {LANG_NAMES.get(body.lang, 'English')} in under 50 words "
                                          f"using ONLY these facts. If the facts don't answer it, say support will call. FACTS: {facts}"},
            {"role": "user", "content": body.question[:300]},
        ], max_tokens=200, temperature=0.2)
        answer, model = text.strip(), info.model
    except LLMUnavailable:
        pass
    return {"answer": answer, "model": model}


@router.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...), lang: str = Form("")):
    data = await audio.read(10 * 1024 * 1024)
    try:
        text = get_router().transcribe(data, audio.filename or "speech.webm", lang[:2] or None)
    except LLMUnavailable as err:
        raise HTTPException(503, str(err)) from err
    return {"text": text}
