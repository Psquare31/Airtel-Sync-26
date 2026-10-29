"""Format checks and cross-document matching for Smart KYC."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date

from rapidfuzz import fuzz

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{3}[ABCFGHLJPTX][A-Z][0-9]{4}[A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")

# GST state codes (first two digits of a GSTIN)
GST_STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}
# Udyam numbers carry a 2-letter state code
UDYAM_STATE_CODES = {
    "JK": "Jammu and Kashmir", "HP": "Himachal Pradesh", "PB": "Punjab", "CH": "Chandigarh",
    "UK": "Uttarakhand", "HR": "Haryana", "DL": "Delhi", "RJ": "Rajasthan", "UP": "Uttar Pradesh",
    "BR": "Bihar", "SK": "Sikkim", "AR": "Arunachal Pradesh", "NL": "Nagaland", "MN": "Manipur",
    "MZ": "Mizoram", "TR": "Tripura", "ML": "Meghalaya", "AS": "Assam", "WB": "West Bengal",
    "JH": "Jharkhand", "OD": "Odisha", "CG": "Chhattisgarh", "MP": "Madhya Pradesh", "GJ": "Gujarat",
    "DN": "Dadra and Nagar Haveli and Daman and Diu", "MH": "Maharashtra", "KR": "Karnataka",
    "GA": "Goa", "LD": "Lakshadweep", "KL": "Kerala", "TN": "Tamil Nadu", "PY": "Puducherry",
    "AN": "Andaman and Nicobar Islands", "TS": "Telangana", "AP": "Andhra Pradesh", "LA": "Ladakh",
}

PASS, WARN, FAIL = "pass", "warn", "fail"


@dataclass
class Check:
    id: str
    status: str
    message: str
    doc: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = GSTIN_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def normalize_id(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z-]", "", value or "").upper()


def validate_gstin(gstin: str) -> list[str]:
    """Returns a list of problems; empty means the format is valid."""
    g = normalize_id(gstin)
    if not g:
        return ["GSTIN is missing"]
    if len(g) != 15:
        return [f"GSTIN must have 15 characters, found {len(g)}"]
    problems = []
    if not GSTIN_RE.match(g):
        problems.append("GSTIN does not follow the standard structure")
    if g[:2] not in GST_STATE_CODES:
        problems.append(f"'{g[:2]}' is not a valid GST state code")
    if not PAN_RE.match(g[2:12]):
        problems.append("The PAN inside the GSTIN is not valid")
    if all(c in GSTIN_CHARS for c in g[:14]) and gstin_checksum(g[:14]) != g[14]:
        problems.append("GSTIN check digit is wrong (likely a typo or altered number)")
    return problems


def validate_udyam(number: str) -> list[str]:
    u = normalize_id(number)
    if not u:
        return ["Udyam registration number is missing"]
    if not UDYAM_RE.match(u):
        return ["Udyam number must look like UDYAM-XX-00-0000000"]
    if u[6:8] not in UDYAM_STATE_CODES:
        return [f"'{u[6:8]}' is not a valid state code in the Udyam number"]
    return []


def gst_state(gstin: str) -> str | None:
    return GST_STATE_CODES.get(normalize_id(gstin)[:2])


def udyam_state(number: str) -> str | None:
    return UDYAM_STATE_CODES.get(normalize_id(number)[6:8])


_PROP_RE = re.compile(r"\(\s*prop\.?\s*(.+?)\)", re.I)
_SUFFIXES = re.compile(r"\b(llp|pvt|private|ltd|limited|and|&|co|company|the)\b", re.I)


def legal_parts(legal_name: str) -> tuple[str, str | None]:
    """'Neha Kaur (Prop. Vindhya Tours)' -> ('Neha Kaur', 'Vindhya Tours')."""
    m = _PROP_RE.search(legal_name or "")
    if m:
        return legal_name[: m.start()].strip(), m.group(1).strip()
    return (legal_name or "").strip(), None


def _norm_name(s: str) -> str:
    s = _SUFFIXES.sub(" ", (s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


def name_similarity(a: str, b: str) -> int:
    """0-100. 'Person (Prop. Business)' names are compared part by part."""
    if not a or not b:
        return 0
    pa, ba = legal_parts(a)
    pb, bb = legal_parts(b)
    if ba and bb:
        return min(name_similarity(pa, pb), name_similarity(ba, bb))
    na, nb = _norm_name(a), _norm_name(b)
    if na == nb:
        return 100
    return int(fuzz.ratio(na, nb))


def _norm_addr(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def address_similarity(a: str, b: str) -> int:
    if not a or not b:
        return 0
    return int(fuzz.ratio(_norm_addr(a), _norm_addr(b)))


PIN_RE = re.compile(r"\b(\d{6})\b")


def pincode(addr: str) -> str | None:
    m = PIN_RE.search((addr or "").replace(" ", " "))
    return m.group(1) if m else None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def mask(value: str | None, keep_start: int = 2, keep_end: int = 3) -> str:
    """Masks identifiers for UI and logs: 37IHKXV5167L1ZS -> 37••••••••••1ZS."""
    if not value:
        return ""
    if len(value) <= keep_start + keep_end:
        return "•" * len(value)
    return value[:keep_start] + "•" * (len(value) - keep_start - keep_end) + value[-keep_end:]
