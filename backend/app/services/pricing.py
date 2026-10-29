"""One transparent monthly price for a bundle.

Catalogue prices are ranges; the point in the range is set by contract
length (longer commitment, lower price). Setup fees are shown separately and
can be spread over 6 months. GST (18%) is shown, never hidden.
"""
from __future__ import annotations

import math

from app.data.loader import Product, get_dataset

GST_RATE = 0.18
CONTRACT_OPTIONS = (12, 24)
SETUP_EMI_MONTHS = 6


def unit_price(p: Product, contract_months: int) -> int:
    term = max(contract_months, p.min_contract_months)
    if term >= 24:
        frac = 1.0
    elif term >= 12:
        frac = 0.5
    else:
        frac = 0.0
    price = p.price_max - (p.price_max - p.price_min) * frac
    return int(math.ceil(price / 10.0) * 10 - 1) if price > 100 else int(round(price))


def price_quote(rec, prof=None, contract_months: int = 12, toggles: dict[str, bool] | None = None,
                quantities: dict[str, int] | None = None, setup_emi: bool = False) -> dict:
    """rec: Recommendation or dict with 'lines'. Returns a fully priced quote."""
    products = get_dataset().products
    lines = rec["lines"] if isinstance(rec, dict) else [l.__dict__ for l in rec.lines]
    toggles = toggles or {}
    quantities = quantities or {}

    chosen = {}
    for l in lines:
        sel = toggles.get(l["product_id"], l["selected"])
        if l.get("locked"):
            sel = False
        if l.get("core"):
            sel = True if not l.get("locked") else False
        chosen[l["product_id"]] = sel

    # dependency enforcement: auto-add/deselect with a message
    messages = []
    for l in lines:
        pid = l["product_id"]
        p = products[pid]
        if chosen[pid] and p.requires_one_of and not any(chosen.get(d) for d in p.requires_one_of):
            base = next((d for d in p.requires_one_of if d in chosen and not _locked(lines, d)), None)
            if base:
                chosen[base] = True
                messages.append(f"{products[base].name} was added because {p.name} needs it.")
            else:
                chosen[pid] = False
                messages.append(f"{p.name} needs an internet line in the bundle.")

    items, monthly, setup = [], 0, 0
    max_term = contract_months
    for l in lines:
        pid = l["product_id"]
        p = products[pid]
        qty = max(1, int(quantities.get(pid, l["qty"])))
        up = unit_price(p, contract_months)
        line_monthly = up * qty
        line_setup = p.setup_fee * qty
        term = max(contract_months, p.min_contract_months)
        item = {
            "product_id": pid,
            "name": p.name,
            "category": p.category,
            "description": p.description,
            "unit": p.unit,
            "qty": qty,
            "unit_price": up,
            "monthly": line_monthly,
            "setup": line_setup,
            "term_months": term,
            "install_days": p.install_days,
            "selected": chosen[pid],
            "core": bool(l.get("core")),
            "locked": bool(l.get("locked")),
            "lock_reason": l.get("lock_reason"),
            "reason": l.get("reason"),
            "reason_code": l.get("reason_code"),
        }
        items.append(item)
        if chosen[pid]:
            monthly += line_monthly
            setup += line_setup
            max_term = max(max_term, term)

    setup_monthly = int(math.ceil(setup / SETUP_EMI_MONTHS)) if setup_emi and setup else 0
    gst = int(round(monthly * GST_RATE))
    return {
        "contract_months": contract_months,
        "contract_options": list(CONTRACT_OPTIONS),
        "items": items,
        "monthly_total": monthly,
        "monthly_gst": gst,
        "monthly_with_gst": monthly + gst,
        "setup_total": setup,
        "setup_emi": setup_emi,
        "setup_emi_monthly": setup_monthly,
        "first_bill_estimate": monthly + gst + (setup_monthly if setup_emi else setup),
        "longest_term_months": max_term,
        "activation_days": max([i["install_days"] for i in items if i["selected"]] or [0]),
        "messages": messages,
    }


def _locked(lines, pid) -> bool:
    return any(l["product_id"] == pid and l.get("locked") for l in lines)
