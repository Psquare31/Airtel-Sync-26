"""Smart KYC: per-document checks plus cross-document and registry checks.

Outcome per applicant:
  verified  - every check passed (warnings allowed)
  fixable   - the owner can fix it themselves (re-upload, add a missing doc)
  blocked   - cannot proceed online (e.g. cancelled GSTIN); hand off to a human
"""
from __future__ import annotations

import hashlib
import io
from datetime import date

import numpy as np
from PIL import Image

from app.config import get_settings
from app.data.loader import get_dataset
from app.services import validators as v
from app.services.validators import FAIL, PASS, WARN, Check

REQUIRED_DOCS = ("gst_certificate", "signatory_id", "address_proof")
OPTIONAL_DOCS = ("udyam_certificate",)
DOC_LABELS = {
    "gst_certificate": "GST registration certificate",
    "udyam_certificate": "Udyam registration certificate",
    "signatory_id": "Authorised signatory ID",
    "address_proof": "Address proof (utility bill)",
}
BLUR_THRESHOLD = 80.0

SIGNING_ROLES = {
    "proprietorship": {"owner", "proprietor", "proprietress"},
    "limited liability partnership": {"partner", "designated partner"},
    "partnership": {"partner", "managing partner"},
    "private limited company": {"director", "managing director", "authorised signatory", "company secretary"},
    "public limited company": {"director", "managing director", "authorised signatory", "company secretary"},
}

# characters OCR / people commonly confuse, by position type
_TO_LETTER = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
_TO_DIGIT = {v_: k for k, v_ in _TO_LETTER.items()}
# GSTIN layout: 2 digits, 5 letters, 4 digits, letter, entity code, 'Z', check
_GSTIN_KINDS = "DDLLLLLDDDDLAZA"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sharpness(image_bytes: bytes) -> float:
    im = Image.open(io.BytesIO(image_bytes)).convert("L")
    if im.width > 1100:
        im = im.resize((1100, int(im.height * 1100 / im.width)))
    a = np.asarray(im).astype(np.float32)
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


def repair_gstin(raw: str) -> tuple[str, bool]:
    """Fixes O/0-style confusions when the repaired number passes the checksum."""
    g = v.normalize_id(raw)
    if len(g) != 15 or not v.validate_gstin(g):
        return g, False
    fixed = []
    for ch, kind in zip(g, _GSTIN_KINDS):
        if kind == "D":
            fixed.append(_TO_DIGIT.get(ch, ch))
        elif kind == "L":
            fixed.append(_TO_LETTER.get(ch, ch))
        elif kind == "Z":  # the 14th character is always 'Z'
            fixed.append("Z" if ch in "Z2" else ch)
        else:
            fixed.append(ch)
    candidate = "".join(fixed)
    if not v.validate_gstin(candidate):
        return candidate, True
    # check digit itself may be misread
    for alt in {candidate[:14] + _TO_LETTER.get(candidate[14], candidate[14]),
                candidate[:14] + _TO_DIGIT.get(candidate[14], candidate[14])}:
        if not v.validate_gstin(alt):
            return alt, True
    return g, False


def document_checks(doc_type: str, extraction: dict, image_bytes: bytes | None = None) -> list[Check]:
    """Checks that need only the one document."""
    label = DOC_LABELS.get(doc_type, doc_type)
    checks: list[Check] = []
    if extraction.get("extractor") == "unavailable":
        return [Check("reader_busy", FAIL, f"Our document reader is busy right now. Please upload the {label} again in a minute.", doc_type)]
    if image_bytes is not None:
        s = sharpness(image_bytes)
        if s < BLUR_THRESHOLD:
            checks.append(Check("image_quality", FAIL, f"The {label} photo is too blurry to read. Please retake it in good light.", doc_type))
            return checks
    detected = extraction.get("detected_type")
    if detected and detected not in (doc_type, "other"):
        checks.append(Check("doc_type", FAIL, f"This looks like a {DOC_LABELS.get(detected, detected)}, not a {label}.", doc_type))
    if extraction.get("legible") is False:
        checks.append(Check("legible", FAIL, f"We couldn't read the {label}. Please upload a clearer copy.", doc_type))
    return checks


def _get(docs: dict, doc_type: str, field: str) -> str:
    return ((docs.get(doc_type) or {}).get("fields") or {}).get(field, "") or ""


def verify(docs: dict[str, dict], declared: dict | None = None) -> dict:
    """docs: doc_type -> {fields, detected_type, checks(list of dict)}; declared: gstin/udyam typed by owner."""
    ds = get_dataset()
    settings = get_settings()
    today = date.fromisoformat(settings.reference_date)
    declared = declared or {}
    checks: list[Check] = []
    registry: dict = {}

    for doc_type, d in docs.items():
        checks.extend(Check(**c) for c in d.get("checks", []))

    for doc_type in REQUIRED_DOCS:
        if doc_type not in docs:
            checks.append(Check("missing_" + doc_type, FAIL, f"{DOC_LABELS[doc_type]} is missing.", doc_type))

    # an unreadable photo already asks for a retake; don't pile field errors on top
    unreadable = {t for t, d in docs.items()
                  if any(c.get("id") in ("image_quality", "legible", "reader_busy") and c.get("status") == FAIL for c in d.get("checks", []))}

    # --- GSTIN
    gstin_raw = _get(docs, "gst_certificate", "gstin") or declared.get("gstin", "")
    gst_rec = None
    if ("gst_certificate" in docs and "gst_certificate" not in unreadable) or declared.get("gstin"):
        gstin, repaired = repair_gstin(gstin_raw)
        problems = v.validate_gstin(gstin)
        if problems:
            checks.append(Check("gstin_format", FAIL, "; ".join(problems) + ".", "gst_certificate"))
        else:
            checks.append(Check("gstin_format", PASS, "GSTIN format and check digit are valid"
                                + (" (we corrected an O/0 reading)." if repaired else "."), "gst_certificate"))
            gst_rec = ds.gstin.get(gstin)
            if not gst_rec:
                checks.append(Check("gstin_registry", FAIL, "This GSTIN is not in the GST registry.", "gst_certificate"))
            else:
                registry["gstin"] = {k: gst_rec[k] for k in ("legal_name", "trade_name", "constitution", "status", "state")}
                status = gst_rec["status"]
                if status != "Active":
                    checks.append(Check("gstin_status", FAIL, f"The GST registration is {status.lower()}. "
                                        "Services that need GST can't be activated online.", "gst_certificate"))
                else:
                    checks.append(Check("gstin_status", PASS, "GST registration is active.", "gst_certificate"))
            if declared.get("gstin") and v.normalize_id(declared["gstin"]) != gstin:
                checks.append(Check("gstin_declared", FAIL, "The GSTIN you typed doesn't match the certificate.", "gst_certificate"))

    if gst_rec and "gst_certificate" in docs:
        for field, reg_field, label in (("legal_name", "legal_name", "Legal name"), ("trade_name", "trade_name", "Trade name")):
            on_doc = _get(docs, "gst_certificate", field)
            if not on_doc:
                continue
            score = v.name_similarity(on_doc, gst_rec[reg_field])
            if score < 85:
                checks.append(Check(f"gst_{field}", FAIL, f"{label} on the certificate (\"{on_doc}\") doesn't match the GST registry "
                                    f"(\"{gst_rec[reg_field]}\"). The document may be outdated or edited.", "gst_certificate"))
        addr = _get(docs, "gst_certificate", "address")
        if addr and v.address_similarity(addr, gst_rec["principal_place_of_business"]) < 80:
            checks.append(Check("gst_address", WARN, "Address on the certificate differs from the GST registry.", "gst_certificate"))
        if not any(c.id in ("gst_legal_name", "gst_trade_name") for c in checks):
            checks.append(Check("gst_names", PASS, "Names match the GST registry.", "gst_certificate"))

    # --- Udyam (optional, but if uploaded it must be valid)
    udyam_rec = None
    if "udyam_certificate" in docs and "udyam_certificate" not in unreadable:
        number = v.normalize_id(_get(docs, "udyam_certificate", "udyam_number"))
        problems = v.validate_udyam(number)
        if problems:
            checks.append(Check("udyam_format", FAIL, problems[0] + " on the Udyam certificate.", "udyam_certificate"))
        else:
            udyam_rec = ds.udyam.get(number)
            if not udyam_rec:
                checks.append(Check("udyam_registry", FAIL, "This Udyam number is not in the Udyam registry.", "udyam_certificate"))
            else:
                registry["udyam"] = {k: udyam_rec[k] for k in ("enterprise_name", "enterprise_type", "major_activity", "state", "city")}
                name = _get(docs, "udyam_certificate", "enterprise_name")
                if name and v.name_similarity(name, udyam_rec["enterprise_name"]) < 85:
                    checks.append(Check("udyam_name", FAIL, "Enterprise name doesn't match the Udyam registry.", "udyam_certificate"))
                else:
                    checks.append(Check("udyam_registry", PASS, f"Udyam registration found ({udyam_rec['enterprise_type']} enterprise).", "udyam_certificate"))
                if gst_rec:
                    trade = gst_rec["trade_name"]
                    if v.name_similarity(udyam_rec["enterprise_name"], trade) < 85:
                        checks.append(Check("udyam_vs_gst", FAIL, "Udyam enterprise name doesn't match the GST trade name.", "udyam_certificate"))
                    if v.udyam_state(number) and v.udyam_state(number) != gst_rec["state"]:
                        checks.append(Check("udyam_state", WARN, "Udyam and GST registrations are in different states.", "udyam_certificate"))
    elif declared.get("has_udyam"):
        checks.append(Check("missing_udyam_certificate", WARN, "You mentioned a Udyam registration; uploading it can unlock MSME offers.", "udyam_certificate"))

    business_name = (gst_rec or {}).get("trade_name") or (udyam_rec or {}).get("enterprise_name") or _get(docs, "gst_certificate", "trade_name")
    constitution = ((gst_rec or {}).get("constitution") or _get(docs, "gst_certificate", "constitution")).lower()
    legal_name = (gst_rec or {}).get("legal_name") or _get(docs, "gst_certificate", "legal_name")

    # --- Signatory
    if "signatory_id" in docs and "signatory_id" not in unreadable:
        name = _get(docs, "signatory_id", "name")
        role = _get(docs, "signatory_id", "designation").lower().strip()
        for_business = _get(docs, "signatory_id", "business_name")
        valid_till = v.parse_date(_get(docs, "signatory_id", "valid_till"))
        if valid_till and valid_till < today:
            checks.append(Check("id_expired", FAIL, f"The signatory ID expired on {valid_till.isoformat()}.", "signatory_id"))
        if for_business and business_name and v.name_similarity(for_business, business_name) < 85:
            checks.append(Check("id_business", FAIL, "The signatory ID is issued for a different business.", "signatory_id"))
        if constitution == "proprietorship":
            proprietor, _ = v.legal_parts(legal_name)
            if proprietor and v.name_similarity(name, proprietor) < 85:
                checks.append(Check("signatory_person", FAIL, f"For a proprietorship the proprietor ({proprietor}) must sign, "
                                    f"but the ID is for {name}.", "signatory_id"))
            else:
                checks.append(Check("signatory_person", PASS, "Signatory is the registered proprietor.", "signatory_id"))
        elif constitution in SIGNING_ROLES:
            if role not in SIGNING_ROLES[constitution]:
                checks.append(Check("signatory_role", FAIL, f"'{role.title() or 'Unknown'}' can't sign for a {constitution.title()}. "
                                    "We need a partner/director, or an authorisation letter signed by one.", "signatory_id"))
            else:
                checks.append(Check("signatory_role", PASS, f"{role.title()} is an authorised signing role.", "signatory_id"))

    # --- Address proof
    if "address_proof" in docs and "address_proof" not in unreadable:
        bill_date = v.parse_date(_get(docs, "address_proof", "bill_date"))
        if not bill_date:
            checks.append(Check("address_date", FAIL, "We couldn't read the bill date on the address proof.", "address_proof"))
        else:
            age = (today - bill_date).days
            if age > settings.address_proof_max_age_days:
                checks.append(Check("address_date", FAIL, f"The address proof is dated {bill_date.isoformat()} ({age} days old). "
                                    f"Please upload one from the last {settings.address_proof_max_age_days} days.", "address_proof"))
            elif age < 0:
                checks.append(Check("address_date", FAIL, "The address proof is dated in the future.", "address_proof"))
            else:
                checks.append(Check("address_date", PASS, f"Address proof is recent ({age} days old).", "address_proof"))
        billed = _get(docs, "address_proof", "billed_to")
        names = [n for n in (business_name, legal_name, v.legal_parts(legal_name)[0]) if n]
        if billed and names and max(v.name_similarity(billed, n) for n in names) < 80:
            checks.append(Check("address_name", FAIL, f"The bill is in the name of \"{billed}\", not the business.", "address_proof"))
        addr = _get(docs, "address_proof", "address")
        ref_addr = (gst_rec or {}).get("principal_place_of_business") or _get(docs, "gst_certificate", "address")
        if addr and ref_addr:
            pin_a, pin_b = v.pincode(addr), v.pincode(ref_addr)
            sim = v.address_similarity(addr, ref_addr)
            if (pin_a and pin_b and pin_a != pin_b) or sim < 70:
                checks.append(Check("address_match", FAIL, "The address on the bill doesn't match the GST registered address.", "address_proof"))
            else:
                checks.append(Check("address_match", PASS, "Address matches the GST registration.", "address_proof"))

    fails = [c for c in checks if c.status == FAIL]
    blocking_ids = {"gstin_status", "gstin_registry", "gst_legal_name", "gst_trade_name", "udyam_vs_gst", "id_business"}
    if not fails:
        outcome = "verified"
    elif any(c.id in blocking_ids for c in fails):
        outcome = "blocked"
    else:
        outcome = "fixable"
    return {
        "outcome": outcome,
        "checks": [c.to_dict() for c in _dedupe(checks)],
        "registry": registry,
        "business_name": business_name,
        "constitution": constitution,
        "gstin_masked": v.mask(v.normalize_id(gstin_raw)) if gstin_raw else "",
    }


def _dedupe(checks: list[Check]) -> list[Check]:
    seen, out = set(), []
    order = {FAIL: 0, WARN: 1, PASS: 2}
    for c in sorted(checks, key=lambda c: order[c.status]):
        if c.id in seen:
            continue
        seen.add(c.id)
        out.append(c)
    return out
