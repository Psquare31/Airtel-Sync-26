"""Lead propensity: P(activation) from facts known when the lead arrives.

Trained on smb_leads.csv at startup (5k rows, < 1 s). Funnel stage, dates and
drop reasons are excluded to avoid leakage.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
    n_leads: int = 0
    n_live: int = 0
    trained_at: str = ""

    def score(self, df: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(_features(df))[:, 1]


LANG_NAMES = {"en": "English", "hi": "Hindi", "hinglish": "Hindi", "ta": "Tamil", "mr": "Marathi", "te": "Telugu",
              "bn": "Bengali", "kn": "Kannada", "gu": "Gujarati", "ml": "Malayalam", "pa": "Punjabi"}
STALE_AFTER = timedelta(days=7)
RETRAIN_EVERY_S = 6 * 3600

_model: PropensityModel | None = None
_trained_at = 0.0


def journey_rows(journeys) -> pd.DataFrame:
    """Live journeys in the leads-file schema, so one model scores both."""
    from app.data.loader import SEGMENT_NAMES

    rows = []
    for j in journeys:
        p = j.profile or {}
        rows.append({
            "lead_id": j.id,
            "lead_source": "Digital advisor" + (" (partner)" if j.partner_code else ""),
            "segment": SEGMENT_NAMES.get(p.get("segment") or j.segment or "", "Micro retail & services"),
            "city_tier": p.get("city_tier") or 2,
            "preferred_language": LANG_NAMES.get(j.lang, "English"),
            "annual_turnover_band": "NA",
            "has_gstin": "Y" if p.get("has_gstin") else "N",
            "has_udyam": "Y" if p.get("has_udyam") else "N",
            "current_internet": p.get("current_internet") or "NA",
            "current_provider": "NA",
            "employee_count": p.get("employees") or 1,
            "num_sites": p.get("sites") or 1,
            "monthly_telecom_spend_inr": p.get("current_spend") or 0,
            "products_of_interest": ";".join(p.get("needs") or []) or None,
        })
    return pd.DataFrame(rows)


def _live_outcomes() -> tuple[pd.DataFrame, np.ndarray]:
    """Journeys with a known outcome: ordered = 1; handed off or idle for a week = 0."""
    from sqlmodel import select

    from app.db import Journey, now, session

    with session() as s:
        journeys = s.exec(select(Journey)).all()
    t = now()
    labelled, y = [], []
    for j in journeys:
        updated = j.updated_at if j.updated_at.tzinfo else j.updated_at.replace(tzinfo=t.tzinfo)
        if j.order_id:
            labelled.append(j); y.append(1)
        elif j.handoff_reason or updated < t - STALE_AFTER:
            labelled.append(j); y.append(0)
    return journey_rows(labelled), np.array(y, dtype=int)


def train(include_live: bool = True) -> PropensityModel:
    leads = get_dataset().leads
    X = _features(leads)
    y = (leads["outcome"] == "Activated").astype(int).values
    n_live = 0
    if include_live:
        try:
            live, live_y = _live_outcomes()
        except Exception as err:  # noqa: BLE001 - a DB hiccup must not stop scoring
            log.warning("live outcomes unavailable: %s", err)
            live, live_y = pd.DataFrame(), np.array([], dtype=int)
        if len(live):
            X = pd.concat([X, _features(live)], ignore_index=True)
            y = np.concatenate([y, live_y])
            n_live = len(live)
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
    log.info("propensity AUC (5-fold) = %.3f on %d leads + %d live journeys", auc, len(leads), n_live)
    return PropensityModel(pipeline=pipe, auc=auc, base_rate=float(y.mean()), top_factors=factors,
                           n_leads=len(leads), n_live=n_live, trained_at=datetime.now(timezone.utc).isoformat())


def get_model(force: bool = False) -> PropensityModel:
    """Cached model, retrained every few hours so new journey outcomes feed back in."""
    global _model, _trained_at
    if force or _model is None or time.monotonic() - _trained_at > RETRAIN_EVERY_S:
        _model = train()
        _trained_at = time.monotonic()
    return _model


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
