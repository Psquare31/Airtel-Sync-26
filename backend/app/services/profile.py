"""Business profile collected by the advisor."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

Segment = Literal["micro", "prof", "multi", "mfg"]

NEEDS = {
    "internet": "Reliable internet",
    "backup_internet": "Backup internet when the main line is down",
    "dedicated_bandwidth": "Dedicated bandwidth with SLA",
    "mobile_lines": "Business mobile lines",
    "pos_billing": "Billing / POS with UPI and card",
    "whatsapp": "WhatsApp channel and catalogue",
    "sms": "SMS alerts and promotions",
    "website": "Website and domain",
    "email": "Business email on own domain",
    "cloud_backup": "Cloud backup for files",
    "device_security": "Antivirus / ransomware protection",
    "firewall": "Managed firewall",
    "guest_wifi": "Separate Wi-Fi for customers",
    "cctv": "CCTV with mobile viewing",
    "telephony": "Business phone lines / IVR",
    "toll_free": "Toll-free number",
    "static_ip": "Static IP for remote access",
    "central_mgmt": "One dashboard for all sites",
    "iot_machines": "Machine monitoring",
    "fleet": "Vehicle tracking",
}

TIER1_CITIES = {
    "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "chennai", "kolkata", "hyderabad",
    "pune", "ahmedabad", "gurugram", "gurgaon", "noida", "navi mumbai", "thane",
}
TIER2_CITIES = {
    "kochi", "ludhiana", "nagpur", "jaipur", "visakhapatnam", "vizag", "lucknow", "bhopal", "surat",
    "mysuru", "mysore", "coimbatore", "indore", "nashik", "vadodara", "patna", "chandigarh",
    "kanpur", "agra", "varanasi", "madurai", "rajkot", "amritsar", "bhubaneswar", "guwahati",
    "dehradun", "ranchi", "raipur", "thiruvananthapuram", "mangaluru", "vijayawada", "jodhpur",
    "gwalior", "jabalpur", "aurangabad", "meerut", "faridabad", "ghaziabad", "hubli", "trichy",
}

BUSINESS_TYPE_SEGMENTS: list[tuple[str, Segment]] = [
    (r"chain|outlets|branches|stores|franchise|group", "multi"),
    (r"unit|factory|workshop|manufactur|moulding|press|plant|industr|fabricat|mill", "mfg"),
    (r"clinic|dental|doctor|hospital|diagnos|lab|physio|ca firm|chartered|account|law|legal|advocate|"
     r"coaching|tuition|school|architect|real estate|insurance|travel|consult|office|agency|studio",
     "prof"),
    (r"kirana|grocery|shop|store|salon|parlour|pharmacy|chemist|medical|bakery|sweet|boutique|"
     r"optician|repair|hardware|stationery|restaurant|cafe|dhaba|tea|retail|general", "micro"),
]


def guess_segment(business_type: str | None, sites: int | None = None, employees: int | None = None):
    if not business_type:
        return None
    bt = business_type.lower()
    for pattern, seg in BUSINESS_TYPE_SEGMENTS:
        if re.search(pattern, bt):
            if seg in ("micro", "prof") and sites and sites >= 3:
                return "multi"
            return seg
    if sites and sites >= 3:
        return "multi"
    return None


_STOP = {"a", "an", "the", "my", "our", "small", "i", "we", "run", "have", "own", "is", "am", "are", "of"}


def business_phrase(text: str) -> str | None:
    """'I run a dental clinic in Pune' -> 'Dental clinic'."""
    for pattern, _ in BUSINESS_TYPE_SEGMENTS:
        m = re.search(rf"((?:[a-z&-]+\s)?)\w*(?:{pattern})\w*", text.lower())
        if m:
            words = [w for w in m.group(0).split() if w not in _STOP]
            if words:
                return " ".join(words).capitalize()
    return None


def city_tier(city: str | None, known: dict[str, int] | None = None) -> int | None:
    if not city:
        return None
    c = city.strip().lower()
    if known and c in known:
        return known[c]
    if c in TIER1_CITIES:
        return 1
    if c in TIER2_CITIES:
        return 2
    return None


class Profile(BaseModel):
    business_name: str | None = None
    business_type: str | None = None
    segment: Segment | None = None
    employees: int | None = Field(default=None, ge=1, le=5000)
    sites: int | None = Field(default=None, ge=1, le=500)
    city: str | None = None
    city_tier: int | None = Field(default=None, ge=1, le=3)
    has_gstin: bool | None = None
    has_udyam: bool | None = None
    current_internet: str | None = None
    current_spend: int | None = None
    needs: list[str] = Field(default_factory=list)
    mobile_lines: int | None = None
    cameras: int | None = None
    pos_counters: int | None = None
    devices: int | None = None
    vehicles: int | None = None
    machines: int | None = None
    fibre_available: bool | None = None
    budget_monthly: int | None = None

    def merge(self, updates: dict) -> "Profile":
        data = self.model_dump()
        for key, value in (updates or {}).items():
            if key not in data or value in (None, "", []):
                continue
            if key == "needs":
                value = [n for n in value if n in NEEDS]
                data["needs"] = sorted(set(data["needs"]) | set(value))
            else:
                data[key] = value
        try:
            merged = Profile(**data)
        except Exception:  # noqa: BLE001 - ignore a bad slot rather than lose the turn
            clean = {k: v for k, v in data.items() if k in self.model_dump()}
            merged = self.model_copy()
            for k, v in clean.items():
                try:
                    merged = Profile(**{**merged.model_dump(), k: v})
                except Exception:  # noqa: BLE001
                    pass
        if not merged.segment:
            merged.segment = guess_segment(merged.business_type, merged.sites, merged.employees)
        return merged

    def missing(self) -> list[str]:
        """Slots the advisor still has to ask about, in asking order."""
        order = []
        if not self.segment:
            order.append("business_type")
        if self.employees is None:
            order.append("employees")
        if self.sites is None:
            order.append("sites")
        if self.city_tier is None:
            order.append("city")
        if self.has_gstin is None:
            order.append("has_gstin")
        if not self.needs and self.current_internet is None:
            order.append("needs")
        return order

    def ready(self) -> bool:
        return not self.missing()
