"""The onboarding journey as a LangGraph StateGraph.

greet -> advisor (loop) -> recommend -> quote (loop) -> consent -> kyc (loop)
      -> esign -> order -> END
Every human step is an interrupt(); FastAPI resumes with Command(resume=...).
Only advisor/recommend (explanations) and KYC extraction use an LLM.
"""
from __future__ import annotations

import logging
import operator
import re
import sqlite3
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlmodel import select

from app.config import ROOT, get_settings
from app.db import ConsentRecord, Journey, KycDocument, audit, now, session
from app.services import kyc as kyc_service
from app.services import orders
from app.services.advisor import advisor_turn, explain, q
from app.services.pricing import price_quote
from app.services.profile import Profile
from app.services.rules_engine import recommend

log = logging.getLogger("journey")

CONSENT_VERSION = "2026-10-v1"


class JourneyState(TypedDict, total=False):
    journey_id: str
    lang: str
    partner_code: str | None
    stage: str
    messages: Annotated[list[dict], operator.add]
    profile: dict
    recommendation: dict
    explanation: dict
    quote_options: dict
    quote: dict
    consent: dict
    kyc_result: dict
    kyc_attempts: int
    esign_error: str | None
    order_id: str | None
    handoff: dict | None
    last_model: str | None


# ------------------------------------------------------------------ helpers
def _touch(state: JourneyState, **fields: Any) -> None:
    """Mirror key facts to the relational Journey row for back-office views."""
    with session() as s:
        j = s.get(Journey, state["journey_id"])
        if not j:
            return
        for k, v in fields.items():
            setattr(j, k, v)
        j.updated_at = now()
        s.add(j)
        s.commit()


def _handoff(state: JourneyState, reason: str, note: str) -> dict:
    _touch(state, handoff_reason=reason)
    audit("system", "handoff", state["journey_id"], reason=reason)
    return {"reason": reason, "note": note, "at": now().isoformat()}


# ------------------------------------------------------------------ nodes
def greet(state: JourneyState) -> dict:
    lang = state.get("lang", "en")
    return {
        "stage": "advisor",
        "profile": state.get("profile") or {},
        "messages": [{"role": "assistant", "content": q(lang, "greet")}],
        "quote_options": {"contract_months": 12, "toggles": {}, "quantities": {}, "setup_emi": False},
        "kyc_attempts": 0,
    }


def advisor(state: JourneyState) -> dict:
    lang = state.get("lang", "en")
    user = interrupt({"kind": "chat"})
    text = str((user or {}).get("text", "") if isinstance(user, dict) else user).strip()[:1000]
    if not text:
        return {}
    prof = Profile(**(state.get("profile") or {}))
    result = advisor_turn(prof, state.get("messages", []), text, lang)
    new_prof: Profile = result["profile"]
    out: dict = {
        "profile": new_prof.model_dump(),
        "messages": [{"role": "user", "content": text},
                     {"role": "assistant", "content": result["reply"], "model": result["model"]}],
        "last_model": result["model"],
    }
    if result["intent"] == "wants_human":
        out["handoff"] = _handoff(state, "customer_requested_callback", "Owner asked to speak to a person during the advisor chat.")
    _touch(state, segment=new_prof.segment, business_name=new_prof.business_name or new_prof.business_type,
           city=new_prof.city, profile=new_prof.model_dump())
    return out


def after_advisor(state: JourneyState) -> Literal["advisor", "recommend"]:
    return "recommend" if Profile(**(state.get("profile") or {})).ready() else "advisor"


def recommend_node(state: JourneyState) -> dict:
    prof = Profile(**state["profile"])
    rec = recommend(prof).to_dict()
    out: dict = {"recommendation": rec, "stage": "quote"}
    if not rec["eligible"]:
        out["handoff"] = _handoff(state, rec["handoff_reason"] or "not_eligible", rec["notes"][0] if rec["notes"] else "")
        out["stage"] = "handoff"
        out["messages"] = [{"role": "assistant", "content": rec["notes"][0]}]
        return out
    out["explanation"] = explain(rec, prof, state.get("lang", "en"))
    return out


def after_recommend(state: JourneyState) -> Literal["quote", "advisor"]:
    return "quote" if state["recommendation"].get("eligible") else "advisor"


def quote_node(state: JourneyState) -> dict:
    opts = state.get("quote_options") or {}
    prof = Profile(**state["profile"])
    quote = price_quote(state["recommendation"], prof, contract_months=opts.get("contract_months", 12),
                        toggles=opts.get("toggles"), quantities=opts.get("quantities"), setup_emi=opts.get("setup_emi", False))
    _touch(state, stage="quote", monthly_value=quote["monthly_total"])
    action = interrupt({"kind": "quote", "quote": quote})
    action = action if isinstance(action, dict) else {}
    kind = action.get("action")
    if kind == "update":
        new_opts = {**opts}
        if "contract_months" in action and int(action["contract_months"]) in (12, 24):
            new_opts["contract_months"] = int(action["contract_months"])
        if "toggles" in action:
            new_opts["toggles"] = {**opts.get("toggles", {}), **{k: bool(v) for k, v in action["toggles"].items()}}
        if "quantities" in action:
            new_opts["quantities"] = {**opts.get("quantities", {}),
                                      **{k: max(1, min(int(v), 500)) for k, v in action["quantities"].items()}}
        if "setup_emi" in action:
            new_opts["setup_emi"] = bool(action["setup_emi"])
        return {"quote_options": new_opts, "quote": quote, "stage": "quote"}
    if kind == "edit_profile":
        return {"stage": "advisor", "quote": quote,
                "messages": [{"role": "assistant", "content": "Sure, tell me what's changed and I'll redo the plan."}],
                "profile": {**state["profile"], "needs": state["profile"].get("needs", [])}}
    if kind == "talk_to_expert":
        return {"quote": quote, "handoff": _handoff(state, "wants_help_with_quote", "Owner asked for help at the quote step.")}
    if kind == "accept":
        audit("owner", "quote_accepted", state["journey_id"], monthly=quote["monthly_total"])
        return {"quote": quote, "stage": "consent"}
    return {"quote": quote}


def after_quote(state: JourneyState) -> Literal["quote", "consent", "advisor"]:
    return {"consent": "consent", "advisor": "advisor"}.get(state.get("stage", "quote"), "quote")


CONSENT_PURPOSES = {
    "kyc_verification": {
        "required": True,
        "title": "Verify your business",
        "text": "We check your GSTIN/Udyam with government registries and read the documents you upload. "
                "Images are deleted right after reading; we keep only the extracted details.",
        "retention": "Extracted details kept for the life of your account + 8 years (telecom licence rule); images: not stored.",
    },
    "service_activation": {
        "required": True,
        "title": "Set up and bill your services",
        "text": "We use your business name, address and contact to install, activate and bill your services.",
        "retention": "For the life of your account.",
    },
    "marketing": {
        "required": False,
        "title": "Offers and tips (optional)",
        "text": "Occasional WhatsApp/SMS offers for your business. You can stop any time.",
        "retention": "Until you withdraw.",
    },
}


def consent_node(state: JourneyState) -> dict:
    _touch(state, stage="consent")
    answer = interrupt({"kind": "consent", "version": CONSENT_VERSION, "purposes": CONSENT_PURPOSES,
                        "processors": ["Accel Telecom (data fiduciary)", "Groq Inc. (AI document reading, no retention)",
                                       "Mock GST & Udyam registries"],
                        "grievance": "privacy@accelbusiness.example · Grievance officer responds within 7 days"})
    answer = answer if isinstance(answer, dict) else {}
    purposes = {k: bool((answer.get("purposes") or {}).get(k)) for k in CONSENT_PURPOSES}
    if not (purposes["kyc_verification"] and purposes["service_activation"]):
        return {"consent": {"granted": False, "purposes": purposes},
                "handoff": _handoff(state, "consent_declined", "Owner declined online KYC; a partner can verify in person."),
                "stage": "handoff"}
    with session() as s:
        rec = ConsentRecord(journey_id=state["journey_id"], notice_version=CONSENT_VERSION,
                            lang=state.get("lang", "en"), purposes=purposes)
        s.add(rec)
        s.commit()
        s.refresh(rec)
        cid = rec.id
    audit("owner", "consent_granted", state["journey_id"], purposes=purposes, version=CONSENT_VERSION)
    return {"consent": {"granted": True, "purposes": purposes, "id": cid, "version": CONSENT_VERSION}, "stage": "kyc"}


def after_consent(state: JourneyState) -> Literal["kyc", "__end__"]:
    return "kyc" if (state.get("consent") or {}).get("granted") else END


def _load_docs(journey_id: str) -> dict:
    with session() as s:
        rows = s.exec(select(KycDocument).where(KycDocument.journey_id == journey_id)).all()
    docs = {}
    for r in sorted(rows, key=lambda r: r.created_at):
        docs[r.doc_type] = {"fields": r.fields.get("fields", {}), "detected_type": r.detected_type,
                            "checks": r.fields.get("checks", []), "legible": r.fields.get("legible", True)}
    return docs


def kyc_node(state: JourneyState) -> dict:
    _touch(state, stage="kyc")
    prof = state.get("profile") or {}
    needs_gst = any(i["selected"] and i["product_id"] in _gst_products() for i in state["quote"]["items"])
    action = interrupt({"kind": "kyc", "required": list(kyc_service.REQUIRED_DOCS),
                        "optional": list(kyc_service.OPTIONAL_DOCS), "labels": kyc_service.DOC_LABELS,
                        "needs_gstin": needs_gst or bool(prof.get("has_gstin")),
                        "last_result": state.get("kyc_result"), "attempts": state.get("kyc_attempts", 0)})
    action = action if isinstance(action, dict) else {}
    if action.get("action") == "assisted":
        return {"handoff": _handoff(state, "kyc_assist_requested", "Owner asked a partner to collect documents."),
                "stage": "handoff"}
    docs = _load_docs(state["journey_id"])
    declared = {"gstin": action.get("gstin", ""), "has_udyam": prof.get("has_udyam")}
    result = kyc_service.verify(docs, declared)
    audit("system", "kyc_checked", state["journey_id"], outcome=result["outcome"],
          failed=[c["id"] for c in result["checks"] if c["status"] == "fail"])
    out: dict = {"kyc_result": result, "kyc_attempts": state.get("kyc_attempts", 0) + 1}
    if result["outcome"] == "verified":
        out["stage"] = "esign"
    elif result["outcome"] == "blocked":
        out["stage"] = "handoff"
        out["handoff"] = _handoff(state, "kyc_blocked", "; ".join(c["message"] for c in result["checks"] if c["status"] == "fail")[:300])
    else:
        out["stage"] = "kyc"
        if out["kyc_attempts"] >= 3:
            out["handoff"] = _handoff(state, "kyc_repeated_failure", "Three unsuccessful KYC attempts; partner to assist.")
    return out


def _gst_products() -> set[str]:
    from app.data.loader import get_dataset

    return {p.id for p in get_dataset().products.values() if p.requires_gstin}


def after_kyc(state: JourneyState) -> Literal["kyc", "esign", "__end__"]:
    stage = state.get("stage")
    if stage == "esign":
        return "esign"
    if stage == "handoff":
        return END
    return "kyc"


def esign_node(state: JourneyState) -> dict:
    _touch(state, stage="esign")
    answer = interrupt({"kind": "esign", "quote": state["quote"], "business": state["kyc_result"].get("business_name"),
                        "error": state.get("esign_error")})
    answer = answer if isinstance(answer, dict) else {}
    otp = str(answer.get("otp", ""))
    if not re.fullmatch(r"\d{6}", otp):
        return {"esign_error": "Enter the 6-digit OTP sent to your mobile."}
    audit("owner", "esigned", state["journey_id"], method="aadhaar-otp-mock")
    return {"esign_error": None, "stage": "order", "quote_options": {**state["quote_options"], "slot": answer.get("slot")}}


def after_esign(state: JourneyState) -> Literal["esign", "order"]:
    return "order" if state.get("stage") == "order" else "esign"


def order_node(state: JourneyState) -> dict:
    slot = (state.get("quote_options") or {}).get("slot")
    order = orders.create_order(state["journey_id"], state["kyc_result"].get("business_name"), state["quote"], slot)
    _touch(state, stage="ordered", order_id=order.id, business_name=state["kyc_result"].get("business_name"))
    audit("system", "order_created", state["journey_id"], order_id=order.id)
    return {"order_id": order.id, "stage": "ordered"}


# ------------------------------------------------------------------ graph
def build_graph(checkpointer):
    g = StateGraph(JourneyState)
    g.add_node("greet", greet)
    g.add_node("advisor", advisor)
    g.add_node("recommend", recommend_node)
    g.add_node("quote", quote_node)
    g.add_node("consent", consent_node)
    g.add_node("kyc", kyc_node)
    g.add_node("esign", esign_node)
    g.add_node("order", order_node)
    g.add_edge(START, "greet")
    g.add_edge("greet", "advisor")
    g.add_conditional_edges("advisor", after_advisor)
    g.add_conditional_edges("recommend", after_recommend)
    g.add_conditional_edges("quote", after_quote)
    g.add_conditional_edges("consent", after_consent)
    g.add_conditional_edges("kyc", after_kyc)
    g.add_conditional_edges("esign", after_esign)
    g.add_edge("order", END)
    return g.compile(checkpointer=checkpointer)


_graph = None


def make_checkpointer():
    settings = get_settings()
    if settings.database_url.startswith(("postgres://", "postgresql")):
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(settings.postgres_conninfo, max_size=5, open=True,
                              kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        saver = PostgresSaver(pool)
        saver.setup()
        return saver
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(ROOT / "backend" / "checkpoints.db"), check_same_thread=False)
    return SqliteSaver(conn)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(make_checkpointer())
    return _graph


def set_graph(graph) -> None:
    global _graph
    _graph = graph
