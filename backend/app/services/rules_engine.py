"""Deterministic bundle recommendation over the product catalogue.

The LLM never chooses products: it only fills the Profile and explains the
reason codes produced here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.data.loader import Product, get_dataset
from app.services.profile import Profile

# reason code -> plain-language template (English). The LLM localises these.
REASONS = {
    "CORE_CONNECTIVITY": "Fast, unlimited internet is the base of your setup ({name}).",
    "NO_FIBRE_FWA": "Fibre isn't confirmed at your address, so 5G AirFiber gets you online in about 2 days with no digging.",
    "FROM_HOTSPOT": "Replaces the mobile hotspot with {name}, a fixed line that won't drop in the middle of a UPI payment.",
    "FROM_HOME_BB": "Moves you from home broadband to {name}, a business line with priority support and an SLA.",
    "FROM_MIXED": "One provider and one bill for all {sites} sites instead of a different ISP at each.",
    "HIGH_USERS": "With {employees} people online, {name} keeps video calls and cloud apps smooth.",
    "DEDICATED_LINE": "Your machines and ERP need guaranteed bandwidth with an SLA, so a leased line fits better than broadband.",
    "UPTIME_FAILOVER": "If the main line drops, the backup router switches over automatically so UPI, billing and calls keep working.",
    "MOBILE_LINES": "{qty} business mobile line(s) on one bill instead of personal SIMs.",
    "POS_UPI": "GST-ready billing with UPI and card acceptance on a tablet.",
    "WHATSAPP": "A verified WhatsApp channel with your catalogue to take orders and send updates.",
    "SMS": "Bulk SMS for appointment reminders, offers and alerts.",
    "WEBSITE": "Get found on Google with your own website and domain.",
    "EMAIL": "Professional email on your own domain for {qty} user(s), plus documents and video meetings.",
    "BACKUP": "Automatic cloud backup so client records survive a lost laptop or ransomware.",
    "DEVICE_SECURITY": "Protects {qty} device(s) against viruses and ransomware.",
    "FIREWALL": "A managed firewall watched by our security team guards your network.",
    "GUEST_WIFI": "A separate Wi-Fi for customers keeps your billing network safe.",
    "CCTV": "{qty} HD camera(s) with 30-day cloud recording, viewable on your phone.",
    "TELEPHONY": "Business phone lines with IVR and call recording.",
    "TOLL_FREE": "A 1800 number customers can call free.",
    "STATIC_IP": "A fixed IP for remote access to CCTV or office systems.",
    "SDWAN": "Manage all {sites} sites from one dashboard with app-priority routing.",
    "IOT": "Track uptime and energy use for {qty} machine(s).",
    "FLEET": "Live GPS tracking for {qty} vehicle(s).",
    "NEEDS_GSTIN": "Needs an active GSTIN. Add your GSTIN to unlock it.",
    "NEEDS_SIZE": "Offered for businesses with at least {min_employees} employees / {min_sites} sites.",
    "NOT_IN_TIER": "Not yet available in your city.",
    "NEEDS_BASE": "Needs an internet line in the same bundle.",
    "BUDGET_OPTIONAL": "Kept as an optional add-on to stay within your budget.",
}


@dataclass
class Line:
    product_id: str
    name: str
    qty: int
    selected: bool
    core: bool
    reason_code: str
    reason: str
    unit: str = ""
    category: str = ""
    locked: bool = False
    lock_reason: str | None = None


@dataclass
class Recommendation:
    segment: str
    lines: list[Line] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    eligible: bool = True
    handoff_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _eligibility(p: Product, prof: Profile) -> tuple[bool, str | None, str | None]:
    tier = prof.city_tier or 2
    if tier not in p.city_tiers:
        return False, "NOT_IN_TIER", REASONS["NOT_IN_TIER"]
    if (prof.employees or 1) < p.min_employees or (prof.sites or 1) < p.min_sites:
        return False, "NEEDS_SIZE", REASONS["NEEDS_SIZE"].format(
            min_employees=p.min_employees, min_sites=p.min_sites
        )
    if p.requires_gstin and not prof.has_gstin:
        return False, "NEEDS_GSTIN", REASONS["NEEDS_GSTIN"]
    return True, None, None


class _Builder:
    def __init__(self, prof: Profile):
        self.prof = prof
        self.products = get_dataset().products
        self.lines: dict[str, Line] = {}

    def add(self, pid: str, qty: int, code: str, selected: bool = True, core: bool = False, **fmt) -> bool:
        p = self.products[pid]
        qty = max(1, int(qty))
        ok, lock_code, lock_reason = _eligibility(p, self.prof)
        reason = REASONS[code].format(name=p.name, qty=qty, sites=self.prof.sites or 1,
                                      employees=self.prof.employees or 1, **fmt)
        if pid in self.lines:
            line = self.lines[pid]
            line.selected = line.selected or (selected and ok)
            line.core = line.core or core
            return ok
        self.lines[pid] = Line(
            product_id=pid, name=p.name, qty=qty, selected=selected and ok, core=core and ok,
            reason_code=code, reason=reason, unit=p.unit, category=p.category,
            locked=not ok, lock_reason=lock_reason if not ok else None,
        )
        return ok

    def has_base(self, options: tuple[str, ...]) -> bool:
        return any(pid in self.lines and self.lines[pid].selected for pid in options)


def connectivity(b: _Builder) -> str | None:
    prof = b.prof
    seg, emp, sites = prof.segment, prof.employees or 1, prof.sites or 1
    wants_dedicated = "dedicated_bandwidth" in prof.needs
    if (seg == "mfg" or wants_dedicated) and prof.has_gstin:
        if emp >= 60 and b.add("P06", 1, "DEDICATED_LINE", core=True):
            return "P06"
        if emp >= 10 and b.add("P05", 1, "DEDICATED_LINE", core=True):
            return "P05"
    if prof.fibre_available is False and seg in ("micro", "prof"):
        b.add("P04", sites, "NO_FIBRE_FWA", core=True)
        return "P04"
    if seg == "micro":
        b.add("P01", sites, "CORE_CONNECTIVITY", core=True)
        return "P01"
    if emp >= 15 and prof.has_gstin and (prof.city_tier or 2) == 1 and seg in ("prof", "mfg"):
        if b.add("P03", 1, "HIGH_USERS", core=True):
            return "P03"
    pid = "P02" if seg in ("prof", "multi", "mfg") else "P01"
    b.add(pid, sites, "HIGH_USERS" if emp >= 8 else "CORE_CONNECTIVITY", core=True)
    return pid


UPGRADE_REASON = {"Mobile hotspot": "FROM_HOTSPOT", "Home broadband": "FROM_HOME_BB", "Mixed per site": "FROM_MIXED"}


def _explain_upgrade(b: _Builder, pid: str | None) -> None:
    """Ties the core line's reason to what the owner uses today."""
    code = UPGRADE_REASON.get(b.prof.current_internet or "")
    line = b.lines.get(pid or "")
    if code and line and line.core:
        line.reason_code = code
        line.reason = REASONS[code].format(name=line.name, sites=b.prof.sites or 1)


def recommend(prof: Profile) -> Recommendation:
    seg = prof.segment or "micro"
    prof = prof.model_copy(update={"segment": seg})
    rec = Recommendation(segment=seg)
    if prof.city_tier == 3:
        rec.eligible = False
        rec.handoff_reason = "city_not_served"
        rec.notes.append("We don't sell online in your city yet. A local Accel partner will call you with what's available.")
        return rec

    b = _Builder(prof)
    needs = set(prof.needs)
    emp, sites = prof.employees or 1, prof.sites or 1
    users = max(1, min(emp, 50))

    _explain_upgrade(b, connectivity(b))

    # mobile lines
    lines_qty = prof.mobile_lines or (1 if seg == "micro" else max(1, min(emp // 4 + 1, 10)))
    mobile_pid = "P07" if seg == "micro" else "P08"
    b.add(mobile_pid, lines_qty, "MOBILE_LINES", core="mobile_lines" in needs)

    # segment defaults: (need, selected-by-default)
    defaults = {
        "micro": [("pos_billing", False), ("whatsapp", False), ("guest_wifi", False), ("cctv", False), ("website", False)],
        "prof": [("email", True), ("device_security", True), ("cloud_backup", True), ("backup_internet", False),
                 ("static_ip", False), ("telephony", False), ("whatsapp", False)],
        "multi": [("backup_internet", True), ("central_mgmt", True), ("pos_billing", False), ("cctv", False),
                  ("email", False), ("toll_free", False), ("whatsapp", False), ("guest_wifi", False)],
        "mfg": [("email", True), ("device_security", True), ("firewall", True), ("iot_machines", False),
                ("cctv", False), ("static_ip", False), ("fleet", False)],
    }[seg]
    wanted = {n: (n in needs) or sel for n, sel in defaults}
    for n in needs:
        wanted.setdefault(n, True)

    cams = prof.cameras or 2 * sites
    devices = prof.devices or users
    adders = {
        "backup_internet": lambda s: b.add("P09", sites, "UPTIME_FAILOVER", selected=s),
        "pos_billing": lambda s: b.add("P19", prof.pos_counters or sites, "POS_UPI", selected=s),
        "whatsapp": lambda s: b.add("P15", 1, "WHATSAPP", selected=s),
        "sms": lambda s: b.add("P14", 1, "SMS", selected=s),
        "website": lambda s: b.add("P18", 1, "WEBSITE", selected=s),
        "email": lambda s: b.add("P16", users, "EMAIL", selected=s),
        "cloud_backup": lambda s: b.add("P17", 1, "BACKUP", selected=s),
        "device_security": lambda s: b.add("P20", devices, "DEVICE_SECURITY", selected=s),
        "firewall": lambda s: b.add("P21", 1, "FIREWALL", selected=s),
        "guest_wifi": lambda s: b.add("P22", sites, "GUEST_WIFI", selected=s),
        "cctv": lambda s: b.add("P23", cams, "CCTV", selected=s),
        "telephony": lambda s: b.add("P12", max(2, min(emp // 5, 10)), "TELEPHONY", selected=s),
        "toll_free": lambda s: b.add("P13", 1, "TOLL_FREE", selected=s),
        "static_ip": lambda s: b.add("P11", 1, "STATIC_IP", selected=s),
        "central_mgmt": lambda s: b.add("P10", sites, "SDWAN", selected=s),
        "iot_machines": lambda s: b.add("P24", prof.machines or 5, "IOT", selected=s),
        "fleet": lambda s: b.add("P25", prof.vehicles or 2, "FLEET", selected=s),
        "mobile_lines": lambda s: None,
        "internet": lambda s: None,
        "dedicated_bandwidth": lambda s: None,
    }
    for need, sel in wanted.items():
        if need in adders:
            adders[need](sel)

    _resolve_dependencies(b)
    rec.lines = sorted(b.lines.values(), key=lambda l: (not l.core, not l.selected, l.locked, l.product_id))

    locked_gst = [l for l in rec.lines if l.lock_reason == REASONS["NEEDS_GSTIN"]]
    if locked_gst:
        rec.notes.append(
            "Some products need a GSTIN. If you register for GST (free, about a week), "
            f"you can add {', '.join(l.name for l in locked_gst)}."
        )
    if prof.budget_monthly:
        _fit_budget(rec, prof)
    return rec


def _resolve_dependencies(b: _Builder) -> None:
    for line in b.lines.values():
        p = b.products[line.product_id]
        if p.requires_one_of and not b.has_base(p.requires_one_of) and line.selected:
            line.selected = False
            line.locked = True
            line.lock_reason = REASONS["NEEDS_BASE"]


def _fit_budget(rec: Recommendation, prof: Profile) -> None:
    from app.services.pricing import price_quote

    optional = [l for l in rec.lines if l.selected and not l.core]
    # drop the most expensive optional items first until we fit
    while optional:
        total = price_quote(rec, prof, contract_months=12)["monthly_total"]
        if total <= prof.budget_monthly:
            return
        priced = price_quote(rec, prof, contract_months=12)["items"]
        cost = {i["product_id"]: i["monthly"] for i in priced}
        victim = max(optional, key=lambda l: cost.get(l.product_id, 0))
        victim.selected = False
        victim.reason = REASONS["BUDGET_OPTIONAL"]
        victim.reason_code = "BUDGET_OPTIONAL"
        optional.remove(victim)
    if price_quote(rec, prof, contract_months=12)["monthly_total"] > prof.budget_monthly:
        rec.notes.append("Even the essentials are a little above your budget; a 24-month plan lowers the monthly price.")
