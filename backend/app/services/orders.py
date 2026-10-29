"""Order creation and the deterministic tracker state machine."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from app.db import Order, now, session

STAGES = [
    ("placed", "Order placed"),
    ("kyc_verified", "KYC verified"),
    ("feasibility", "Site feasibility confirmed"),
    ("scheduled", "Installation scheduled"),
    ("installed", "Installed"),
    ("activated", "All services active"),
]

NOTIFY = {
    "placed": "Your Accel Business order {id} is confirmed. Track it any time: {link}",
    "kyc_verified": "Documents verified. No more paperwork needed.",
    "feasibility": "Good news: your site is ready for installation.",
    "scheduled": "Engineer visit booked for {slot}. You'll get the engineer's name 1 hour before.",
    "installed": "Installation done. Your lines are being switched on.",
    "activated": "All services are live. One bill, one support number: 121. Welcome to Accel Business!",
}


def _plan(quote: dict, start: datetime) -> tuple[list[dict], int]:
    selected = [i for i in quote.get("items", []) if i.get("selected")]
    install_days = max([i["install_days"] for i in selected] or [1])
    offsets = {
        "placed": 0,
        "kyc_verified": 0,
        "feasibility": 1,
        "scheduled": 1,
        "installed": max(2, install_days),
        "activated": max(2, install_days),
    }
    timeline = [
        {"key": key, "label": label, "eta": (start + timedelta(days=offsets[key])).date().isoformat(),
         "done_at": None}
        for key, label in STAGES
    ]
    return timeline, install_days


def create_order(journey_id: str, business_name: str | None, quote: dict, slot: str | None = None) -> Order:
    start = now()
    timeline, _ = _plan(quote, start)
    order = Order(
        id="AB" + secrets.token_hex(3).upper(),
        journey_id=journey_id,
        business_name=business_name,
        quote=quote,
        timeline=timeline,
        install_slot=slot,
    )
    for step in ("placed", "kyc_verified"):
        _complete(order, step, start)
    with session() as s:
        s.add(order)
        s.commit()
        s.refresh(order)
    return order


def _complete(order: Order, key: str, at: datetime) -> None:
    timeline = [dict(t) for t in order.timeline]
    for i, t in enumerate(timeline):
        if t["key"] == key and not t["done_at"]:
            t["done_at"] = at.isoformat()
            order.stage_index = i
            slot = order.install_slot or (at + timedelta(days=1)).strftime("%d %b, 10am-1pm")
            order.notifications = [
                *order.notifications,
                {"at": at.isoformat(), "channel": "whatsapp",
                 "text": NOTIFY[key].format(id=order.id, link=f"/track/{order.id}", slot=slot)},
            ]
    order.timeline = timeline


def advance(order_id: str) -> Order | None:
    """Demo helper: completes the next stage."""
    with session() as s:
        order = s.get(Order, order_id)
        if not order:
            return None
        pending = [t for t in order.timeline if not t["done_at"]]
        if pending:
            step = pending[0]["key"]
            _complete(order, step, now())
            if step == "installed":
                _complete(order, "activated", now())
        s.add(order)
        s.commit()
        s.refresh(order)
        return order


def get_order(order_id: str) -> Order | None:
    with session() as s:
        return s.get(Order, order_id.upper())


def view(order: Order) -> dict:
    done_keys = {t["key"] for t in order.timeline if t["done_at"]}
    activated = "activated" in done_keys
    installed = "installed" in done_keys
    items = []
    for i in order.quote.get("items", []):
        if not i.get("selected"):
            continue
        # mobile lines and cloud services go live before the site install
        early = i["install_days"] <= 1 and "feasibility" in done_keys
        status = "Active" if activated or early or (installed and i["install_days"] <= 3) else "In progress"
        items.append({"product_id": i["product_id"], "name": i["name"], "qty": i["qty"], "status": status,
                      "install_days": i["install_days"]})
    current = next((t for t in order.timeline if not t["done_at"]), None)
    return {
        "id": order.id,
        "business_name": order.business_name,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "timeline": order.timeline,
        "current": current["label"] if current else "All services active",
        "eta": order.timeline[-1]["eta"],
        "complete": current is None,
        "items": items,
        "notifications": order.notifications,
        "monthly_total": order.quote.get("monthly_total"),
        "monthly_with_gst": order.quote.get("monthly_with_gst"),
        "install_slot": order.install_slot,
    }
