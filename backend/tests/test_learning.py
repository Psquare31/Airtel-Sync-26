from datetime import timedelta

import yaml
from langgraph.types import Command
from sqlmodel import select

from app.db import Journey, LearnedTurn, now, session
from app.services import learning
from app.services.propensity import get_model
from app.services.retention import withdraw


def cfg(jid):
    return {"configurable": {"thread_id": jid}}


def run_to_consent(graph, jid, improvement: bool):
    with session() as s:
        s.add(Journey(id=jid))
        s.commit()
    graph.invoke({"journey_id": jid, "lang": "en", "messages": []}, cfg(jid))
    for text in ["I run a dental clinic in Pune with 6 staff, 1 clinic, we have GST", "home broadband", "email and backup"]:
        graph.invoke(Command(resume={"text": text}), cfg(jid))
    graph.invoke(Command(resume={"action": "accept"}), cfg(jid))
    graph.invoke(Command(resume={"purposes": {"kyc_verification": True, "service_activation": True,
                                              "improvement": improvement}}), cfg(jid))


def turns(jid):
    with session() as s:
        return s.exec(select(LearnedTurn).where(LearnedTurn.journey_id == jid)).all()


def test_turn_entry_keeps_only_changed_slots_and_redacts():
    e = learning.turn_entry("call me on 9876543210, 6 staff", {"employees": None}, {"employees": 6, "sites": None}, "m")
    assert e["updates"] == {"employees": 6} and "9876543210" not in e["text"]
    assert learning.turn_entry("hi", {"a": 1}, {"a": 1}, "m") is None


def test_turns_saved_only_with_improvement_consent(graph):
    run_to_consent(graph, "JNO", improvement=False)
    assert turns("JNO") == []
    run_to_consent(graph, "JYES", improvement=True)
    saved = turns("JYES")
    assert len(saved) >= 2 and all(t.lang == "en" for t in saved)
    assert any("employees" in t.updates for t in saved)


def test_examples_are_similar_and_exclude_flagged(graph):
    run_to_consent(graph, "JEX", improvement=True)
    shots = learning.examples("en", "I run a dental clinic in Delhi with 9 staff")
    assert shots and "dental clinic" in shots[0]["text"]
    assert learning.examples("hi", "I run a dental clinic") == []  # other languages never mix
    learning.record_feedback("JEX", -1, "Too expensive", None)
    assert all(t.flagged for t in turns("JEX"))
    assert learning.examples("en", "I run a dental clinic in Delhi with 9 staff") == []


def test_flagged_conversations_export_as_draft_scenarios(graph):
    run_to_consent(graph, "JFLAG", improvement=True)
    learning.record_feedback("JFLAG", -1, "Missing something", "need cctv too")
    items = yaml.safe_load(learning.export_scenarios())
    item = next(i for i in items if "JFLAG" in i["name"])
    assert item["status"] == "needs_review" and item["messages"] and item["observed"]["sites"] == 1


def test_withdrawing_improvement_deletes_turns(graph):
    run_to_consent(graph, "JWD", improvement=True)
    assert turns("JWD")
    withdraw("JWD", ["improvement"])
    assert turns("JWD") == []


def test_model_retrains_on_live_outcomes():
    with session() as s:
        for i in range(6):
            s.add(Journey(id=f"JL{i}", segment="prof", order_id="AB1" if i % 2 else None,
                          updated_at=now() - timedelta(days=10),
                          profile={"segment": "prof", "employees": 6, "sites": 1, "city_tier": 1, "has_gstin": True}))
        s.commit()
    model = get_model(force=True)
    assert model.n_live == 6 and 0.5 < model.auc < 1 and model.trained_at
