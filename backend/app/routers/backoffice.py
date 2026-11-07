"""Back-office for sales and channel partners: leads the advisor couldn't close."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel
from sqlmodel import select

from app.config import get_settings
from app.data.loader import get_dataset
from app.db import Journey, LeadAction, audit, session
from app.services import learning
from app.services.propensity import RECOVERABLE, explain_row, get_model, journey_rows
from app.services.validators import mask

router = APIRouter(prefix="/api/backoffice", tags=["backoffice"])

HANDOFF_ACTIONS = {
    "customer_requested_callback": "Call back within 2 working hours",
    "wants_help_with_quote": "Call to walk through the quote",
    "city_not_served": "Assign to nearest channel partner",
    "consent_declined": "Partner visit for in-person KYC",
    "kyc_blocked": "Partner to resolve registration issue",
    "kyc_assist_requested": "Partner to collect documents",
    "kyc_repeated_failure": "Partner to collect documents",
    "kyc_mixed_documents": "Verify owner identity in person (documents from different businesses)",
}


def require_staff(x_backoffice_key: str = Header(default="")):
    if x_backoffice_key != get_settings().backoffice_key:
        raise HTTPException(401, "back-office key required")
    return x_backoffice_key


@router.get("/summary", dependencies=[Depends(require_staff)])
def summary():
    leads = get_dataset().leads
    stages = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
    order = {s: i for i, s in enumerate(stages)}
    reached = leads["stage_reached"].map(order)
    funnel = [{"stage": s, "count": int((reached >= i).sum())} for i, s in enumerate(stages)]
    act = leads[leads.outcome == "Activated"]
    with session() as s:
        live = s.exec(select(Journey)).all()
    model = get_model()
    return {
        "funnel": funnel,
        "activation_rate": round(len(act) / len(leads), 4),
        "avg_days_to_activate": round(float(act["days_lead_to_activation"].mean()), 1),
        "avg_followups": round(float(act["customer_follow_up_calls"].mean()), 1),
        "cac_per_activation": int(leads["acquisition_cost_inr"].sum() / max(len(act), 1)),
        "churn_6m": round(float((act["churned_within_6_months"] == "Y").mean()), 3),
        "live_journeys": len(live),
        "live_ordered": sum(1 for j in live if j.order_id),
        "live_handoffs": sum(1 for j in live if j.handoff_reason),
        "model_auc": round(model.auc, 3),
        "model_factors": model.top_factors,
        "model_trained_at": model.trained_at,
        "model_live_rows": model.n_live,
    }


@router.get("/leads", dependencies=[Depends(require_staff)])
def leads(segment: str | None = None, city: str | None = None, source: str | None = None,
          reason: str | None = None, limit: int = Query(50, le=500)):
    out = []
    with session() as s:
        actions = {a.lead_id: a for a in s.exec(select(LeadAction)).all()}
        live = s.exec(select(Journey).where(Journey.handoff_reason.is_not(None))).all()
    live = sorted(live, key=lambda j: j.updated_at, reverse=True)
    live_scores = get_model().score(journey_rows(live)) if live else []
    for j, score in zip(live, live_scores):
        out.append({
            "lead_id": j.id, "source": "Digital advisor" + (f" (partner {j.partner_code})" if j.partner_code else ""),
            "business_name": j.business_name or "New business", "segment": j.segment, "city": j.city,
            "stage": j.stage, "reason": j.handoff_reason, "action": HANDOFF_ACTIONS.get(j.handoff_reason or "", "Call back"),
            "score": round(float(score), 3), "monthly_value": j.monthly_value, "live": True,
            "why": ["Live journey: owner is engaged right now"],
            "assigned": actions[j.id].assigned_to if j.id in actions else None,
        })

    df = get_dataset().leads
    df = df[(df.outcome == "Dropped") & df.drop_reason.isin(RECOVERABLE.keys())]
    if segment:
        df = df[df.segment == segment]
    if city:
        df = df[df.city.str.lower() == city.lower()]
    if source:
        df = df[df.lead_source == source]
    if reason:
        df = df[df.drop_reason == reason]
    scores = get_model().score(df) if len(df) else []
    df = df.assign(score=scores).sort_values("score", ascending=False).head(limit)
    for _, r in df.iterrows():
        out.append({
            "lead_id": r.lead_id, "source": r.lead_source, "business_name": r.business_name, "segment": r.segment,
            "city": r.city, "stage": r.stage_reached, "reason": r.drop_reason, "action": RECOVERABLE[r.drop_reason],
            "score": round(float(r.score), 3), "contact": r.contact_name, "language": r.preferred_language,
            "gstin": mask(r.gstin) if isinstance(r.gstin, str) else None, "employees": int(r.employee_count),
            "sites": int(r.num_sites), "live": False, "why": explain_row(r),
            "assigned": actions[r.lead_id].assigned_to if r.lead_id in actions else None,
        })
    return {"leads": out[: limit + len(live)], "reasons": sorted(RECOVERABLE)}


class AssignBody(BaseModel):
    assigned_to: str
    channel: str = "partner"
    note: str | None = None


@router.post("/leads/{lead_id}/assign")
def assign(lead_id: str, body: AssignBody, key: str = Depends(require_staff)):
    with session() as s:
        s.add(LeadAction(lead_id=lead_id, assigned_to=body.assigned_to[:60], channel=body.channel, note=body.note))
        s.commit()
    audit("staff", "lead_assigned", None, lead_id=lead_id, to=body.assigned_to, channel=body.channel)
    return {"ok": True}


@router.get("/learning", dependencies=[Depends(require_staff)])
def learning_stats():
    model = get_model()
    return {**learning.stats(), "model": {"auc": round(model.auc, 3), "trained_at": model.trained_at,
                                          "live_rows": model.n_live, "lead_rows": model.n_leads}}


@router.get("/learning/scenarios.yaml", dependencies=[Depends(require_staff)])
def learning_scenarios():
    """Thumbs-down conversations as draft advisor test cases."""
    return Response(learning.export_scenarios(), media_type="text/yaml; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=learned_scenarios.yaml"})


@router.post("/model/retrain", dependencies=[Depends(require_staff)])
def retrain():
    model = get_model(force=True)
    audit("staff", "model_retrained", None, auc=round(model.auc, 3), live_rows=model.n_live)
    return {"auc": round(model.auc, 3), "trained_at": model.trained_at, "live_rows": model.n_live}
