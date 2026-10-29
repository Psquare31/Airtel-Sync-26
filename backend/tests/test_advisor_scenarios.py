from pathlib import Path

import pytest
import yaml

from app.services.advisor import advisor_turn
from app.services.pricing import price_quote
from app.services.profile import Profile
from app.services.rules_engine import recommend

SCENARIOS = yaml.safe_load((Path(__file__).parent / "advisor_scenarios.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_scenario(sc):
    prof, history, last, intents = Profile(), [], None, []
    for msg in sc["messages"]:
        last = advisor_turn(prof, history, msg, sc.get("lang", "en"))
        prof = last["profile"]
        intents.append(last["intent"])
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": last["reply"]}]
    exp = sc["expect"]
    if "ready" in exp:
        assert prof.ready() == exp["ready"]
    if "reply_contains" in exp:
        assert exp["reply_contains"] in last["reply"]
    if exp.get("handoff") == "customer_requested_callback":
        assert "wants_human" in intents
        return
    if not any(k in exp for k in ("segment", "must_select", "must_not_select", "locked", "handoff", "max_monthly")):
        return
    assert prof.ready(), f"still missing {prof.missing()} -> {prof}"
    rec = recommend(prof)
    if exp.get("handoff") == "city_not_served":
        assert not rec.eligible
        return
    chosen = {l.product_id for l in rec.lines if l.selected}
    locked = {l.product_id for l in rec.lines if l.locked}
    if "segment" in exp:
        assert rec.segment == exp["segment"]
    assert set(exp.get("must_select", [])) <= chosen, chosen
    assert not set(exp.get("must_not_select", [])) & chosen
    assert set(exp.get("locked", [])) <= locked
    if "max_monthly" in exp:
        assert price_quote(rec, prof)["monthly_total"] <= exp["max_monthly"]
