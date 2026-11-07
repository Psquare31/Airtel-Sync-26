from langgraph.types import Command

from app.db import Journey, KycDocument, session


def cfg(jid):
    return {"configurable": {"thread_id": jid}}


def pending(graph, jid):
    for t in graph.get_state(cfg(jid)).tasks:
        if t.interrupts:
            return t.interrupts[0].value
    return None


def start(graph, jid="JTEST"):
    with session() as s:
        s.add(Journey(id=jid))
        s.commit()
    graph.invoke({"journey_id": jid, "lang": "en", "messages": []}, cfg(jid))
    return jid


def chat_to_quote(graph, jid):
    graph.invoke(Command(resume={"text": "I run a dental clinic in Kolkata with 6 staff, 1 clinic, we have GST, home broadband today"}), cfg(jid))
    if pending(graph, jid)["kind"] == "chat":
        graph.invoke(Command(resume={"text": "email and backup"}), cfg(jid))
    assert pending(graph, jid)["kind"] == "quote"


ADDR = "Shop/Unit 199, Station Road, Kolkata, West Bengal - 347550"


def add_docs(jid, gstin="19EOGXH4115Y1ZL", bill_date="2026-06-01"):
    docs = {
        "gst_certificate": {"gstin": gstin, "legal_name": "Joseph Shah (Prop. Harmony Dental Care)",
                            "trade_name": "Harmony Dental Care", "constitution": "Proprietorship", "address": ADDR},
        "signatory_id": {"name": "Joseph Shah", "designation": "Owner", "business_name": "Harmony Dental Care",
                         "valid_till": "2028-01-01"},
        "address_proof": {"billed_to": "Harmony Dental Care", "address": ADDR, "bill_date": bill_date},
        "udyam_certificate": {"udyam_number": "UDYAM-WB-00-5053330", "enterprise_name": "Harmony Dental Care"},
    }
    with session() as s:
        for t, f in docs.items():
            s.add(KycDocument(journey_id=jid, doc_type=t, sha256="x", fields={"fields": f, "checks": []}))
        s.commit()


def to_kyc(graph, jid):
    chat_to_quote(graph, jid)
    graph.invoke(Command(resume={"action": "update", "contract_months": 24}), cfg(jid))
    assert pending(graph, jid)["quote"]["contract_months"] == 24
    graph.invoke(Command(resume={"action": "accept"}), cfg(jid))
    assert pending(graph, jid)["kind"] == "consent"
    graph.invoke(Command(resume={"purposes": {"kyc_verification": True, "service_activation": True}}), cfg(jid))
    assert pending(graph, jid)["kind"] == "kyc"


def test_happy_path_to_order(graph):
    from app.services.orders import advance, get_order, view

    jid = start(graph)
    to_kyc(graph, jid)
    add_docs(jid)
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    assert pending(graph, jid)["kind"] == "esign"
    graph.invoke(Command(resume={"otp": "12"}), cfg(jid))
    assert pending(graph, jid)["error"]
    graph.invoke(Command(resume={"otp": "123456"}), cfg(jid))
    state = graph.get_state(cfg(jid)).values
    assert state["stage"] == "ordered" and state["order_id"]
    order = get_order(state["order_id"])
    assert view(order)["timeline"][1]["done_at"]
    for _ in range(4):
        advance(order.id)
    assert view(get_order(order.id))["complete"]


def test_kyc_fail_then_fix(graph):
    jid = start(graph, "JFIX")
    to_kyc(graph, jid)
    add_docs(jid, bill_date="2025-01-01")
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    p = pending(graph, jid)
    assert p["kind"] == "kyc" and p["last_result"]["outcome"] == "fixable"
    add_docs(jid)  # newer uploads win
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    assert pending(graph, jid)["kind"] == "esign"


def test_cancelled_gstin_hands_off(graph):
    jid = start(graph, "JBLK")
    to_kyc(graph, jid)
    addr = "Shop/Unit 1, Tech Park Road, Visakhapatnam, Andhra Pradesh - 118383"
    with session() as s:
        s.add(KycDocument(journey_id=jid, doc_type="gst_certificate", sha256="x", fields={"fields": {
            "gstin": "37IHKXV5167L1ZS", "legal_name": "Neha Kaur (Prop. Vindhya Tours & Travels)",
            "trade_name": "Vindhya Tours & Travels", "address": addr}}))
        s.commit()
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    state = graph.get_state(cfg(jid)).values
    assert state["stage"] == "handoff" and state["handoff"]["reason"] == "kyc_blocked"
    assert pending(graph, jid) is None
    with session() as s:
        assert s.get(Journey, jid).handoff_reason == "kyc_blocked"



def add_foreign_id(jid):
    with session() as s:
        s.add(KycDocument(journey_id=jid, doc_type="signatory_id", sha256="y", fields={"fields": {
            "name": "Neha Kaur", "designation": "Owner", "business_name": "Vindhya Tours & Travels",
            "valid_till": "2028-01-01"}, "checks": []}))
        s.commit()


def test_mixed_documents_get_one_retry_then_person(graph):
    jid = start(graph, "JMIX")
    to_kyc(graph, jid)
    add_docs(jid)
    add_foreign_id(jid)
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    p = pending(graph, jid)
    assert p["kind"] == "kyc" and p["last_result"]["outcome"] == "fixable" and p["last_result"]["mixed_businesses"]
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    state = graph.get_state(cfg(jid)).values
    assert state["stage"] == "handoff" and state["handoff"]["reason"] == "kyc_mixed_documents"


def test_consent_declined(graph):
    jid = start(graph, "JDEC")
    chat_to_quote(graph, jid)
    graph.invoke(Command(resume={"action": "accept"}), cfg(jid))
    graph.invoke(Command(resume={"purposes": {"kyc_verification": False}}), cfg(jid))
    assert graph.get_state(cfg(jid)).values["handoff"]["reason"] == "consent_declined"


def test_language_switch_keeps_the_step_waiting(graph):
    def switch(lang):
        graph.update_state(cfg(jid), {"lang": lang})
        graph.invoke(None, cfg(jid))
        return pending(graph, jid)

    jid = start(graph, "JLANG")
    assert switch("hi")["kind"] == "chat"
    chat_to_quote(graph, jid)
    graph.invoke(Command(resume={"action": "update", "contract_months": 24}), cfg(jid))
    p = switch("en")
    assert p["kind"] == "quote" and p["quote"]["contract_months"] == 24  # edits survive
    graph.invoke(Command(resume={"action": "accept"}), cfg(jid))
    assert switch("hi")["kind"] == "consent"
    graph.invoke(Command(resume={"purposes": {"kyc_verification": True, "service_activation": True}}), cfg(jid))
    assert switch("en")["kind"] == "kyc"
    add_docs(jid)
    graph.invoke(Command(resume={"action": "submit"}), cfg(jid))
    assert switch("hi")["kind"] == "esign"
    assert graph.get_state(cfg(jid)).values["lang"] == "hi"
