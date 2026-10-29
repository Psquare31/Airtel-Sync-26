"""Business-case numbers from smb_leads.csv. usage: python analysis/funnel.py"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "smb_leads.csv"
STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
# drops a self-serve journey removes or shortens
DIGITAL_FIXABLE = {
    "Owner had no time for a visit", "Visit not scheduled by sales", "Quote took too long to arrive",
    "Quote too complex to understand", "Found paperwork too long", "Missing GST or Udyam document",
    "Document details did not match", "Authorised signatory not available",
}


def main() -> None:
    d = pd.read_csv(DATA)
    d["act"] = (d.outcome == "Activated").astype(int)
    a = d[d.act == 1]
    pd.set_option("display.width", 200)

    order = {s: i for i, s in enumerate(STAGES)}
    reached = d.stage_reached.map(order)
    print("FUNNEL")
    prev = None
    for i, s in enumerate(STAGES):
        n = int((reached >= i).sum())
        print(f"  {s:15} {n:5} {'' if prev is None else f'{n / prev:.0%}'}")
        prev = n

    print("\nSEGMENT ECONOMICS")
    seg = d.groupby("segment").agg(leads=("act", "size"), act_rate=("act", "mean"), cac_total=("acquisition_cost_inr", "sum"))
    seg["cac_per_act"] = seg.cac_total / (seg.act_rate * seg.leads)
    seg["median_mrr"] = a.groupby("segment").monthly_bundle_value_inr.median()
    seg["churn_6m"] = a.groupby("segment").churned_within_6_months.apply(lambda s: (s == "Y").mean())
    seg["nps"] = a.groupby("segment").nps_score.mean()
    seg["payback_months"] = seg.cac_per_act / seg.median_mrr
    seg["gstin_share"] = d.groupby("segment").has_gstin.apply(lambda s: (s == "Y").mean())
    print(seg.drop(columns="cac_total").round(3).to_string())

    print("\nSOURCE")
    src = d.groupby("lead_source").agg(leads=("act", "size"), act_rate=("act", "mean"), cost=("acquisition_cost_inr", "sum"))
    src["cac_per_act"] = src.cost / (src.act_rate * src.leads)
    print(src.drop(columns="cost").round(3).to_string())

    print("\nGSTIN", d.groupby("has_gstin").act.mean().round(3).to_dict())
    print("LANGUAGE", d.groupby("preferred_language").act.mean().round(3).sort_values().to_dict())
    drops = d[d.outcome == "Dropped"]
    fixable = drops.drop_reason.isin(DIGITAL_FIXABLE)
    print(f"\nDROPS fixable by digital journey: {fixable.sum()} of {len(drops)} ({fixable.mean():.0%})")
    after_needs = drops[drops.stage_reached.isin(["Needs assessed", "Quote accepted", "KYC complete"])]
    print("drop reasons after needs assessed:\n", after_needs.drop_reason.value_counts().to_string())
    print("\nACTIVATED: days", round(a.days_lead_to_activation.mean(), 1), "follow-ups", round(a.customer_follow_up_calls.mean(), 2),
          "churn", round((a.churned_within_6_months == "Y").mean(), 3), "nps", round(a.nps_score.mean(), 2))
    print("churn by follow-up calls", a.groupby("customer_follow_up_calls").churned_within_6_months.apply(lambda s: round((s == "Y").mean(), 3)).to_dict())
    print("CAC per activation", int(d.acquisition_cost_inr.sum() / len(a)))


if __name__ == "__main__":
    main()
