"""Lead propensity: P(activation) from facts known when the lead arrives.

Trained on smb_leads.csv at startup (5k rows, < 1 s). Funnel stage, dates and
drop reasons are excluded to avoid leakage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.data.loader import get_dataset

log = logging.getLogger("propensity")

CATEGORICAL = ["lead_source", "segment", "city_tier", "preferred_language", "annual_turnover_band", "has_gstin",
               "has_udyam", "current_internet", "current_provider"]
NUMERIC = ["log_employees", "num_sites", "log_spend", "n_interests"]

# drop reasons a digital journey (or a partner) can plausibly recover
RECOVERABLE = {
    "Owner had no time for a visit": "Send the self-serve link on WhatsApp; no visit needed",
    "Visit not scheduled by sales": "Send the self-serve link on WhatsApp; no visit needed",
    "Quote took too long to arrive": "Share an instant digital quote",
    "Quote too complex to understand": "Share the plain-language digital quote",
    "Found paperwork too long": "Invite to 3-minute Smart KYC with DigiLocker",
    "Missing GST or Udyam document": "Partner visit to help with GST/Udyam registration",
    "Authorised signatory not available": "Partner to collect signatory e-sign on site",
    "Document details did not match": "Partner to collect corrected documents",
    "Unreachable after 3 attempts": "Try WhatsApp instead of calls",
    "Decided to wait": "Nurture: WhatsApp reminder with current offer in 30 days",
    "Price too high": "Offer the 24-month price or a smaller starter bundle",
    "Competitor offered cheaper plan": "Offer the 24-month price; highlight one bill and one support number",
}


def _features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["city_tier"] = out["city_tier"].astype(str)
    out["log_employees"] = np.log1p(out["employee_count"].astype(float))
    out["log_spend"] = np.log1p(out["monthly_telecom_spend_inr"].astype(float).fillna(0))
    out["n_interests"] = out["products_of_interest"].fillna("").str.count(";") + out["products_of_interest"].notna()
    for c in CATEGORICAL:
        out[c] = out[c].astype(str).fillna("NA")
    return out[CATEGORICAL + NUMERIC]


@dataclass
class PropensityModel:
    pipeline: Pipeline
    auc: float
    base_rate: float
    top_factors: list[dict]

    def score(self, df: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(_features(df))[:, 1]


@lru_cache
def get_model() -> PropensityModel:
    leads = get_dataset().leads
    y = (leads["outcome"] == "Activated").astype(int).values
    X = _features(leads)
    pipe = Pipeline([
        ("prep", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ])),
        ("lr", LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced")),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
    oof = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]
    auc = float(roc_auc_score(y, oof))
    pipe.fit(X, y)
    names = pipe.named_steps["prep"].get_feature_names_out()
    coefs = pipe.named_steps["lr"].coef_[0]
    order = np.argsort(-np.abs(coefs))[:10]
    factors = [{"feature": names[i].replace("cat__", "").replace("num__", ""), "weight": round(float(coefs[i]), 3)}
               for i in order]
    log.info("propensity AUC (5-fold) = %.3f", auc)
    return PropensityModel(pipeline=pipe, auc=auc, base_rate=float(y.mean()), top_factors=factors)


def explain_row(row: pd.Series) -> list[str]:
    reasons = []
    if row.get("has_gstin") == "Y":
        reasons.append("Has GSTIN (5x higher activation)")
    else:
        reasons.append("No GSTIN yet: needs a GST-free bundle or help registering")
    if row.get("lead_source") in ("Referral", "Inbound call"):
        reasons.append(f"{row['lead_source']} lead: high intent")
    if row.get("segment") in ("Professional offices", "Small multi-site businesses", "Small manufacturers"):
        reasons.append(f"{row['segment']}: higher value segment")
    if row.get("current_internet") in ("Leased line", "Mixed per site"):
        reasons.append("Already pays for business connectivity")
    return reasons[:3]
